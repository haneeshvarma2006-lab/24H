"""MediParse API. Run from the repo root:  uvicorn backend.app:app --reload
Interactive test page: http://127.0.0.1:8000/docs
"""
import csv
import hashlib
import io
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from openpyxl import Workbook
from pydantic import BaseModel

from backend.extract import FIELDS, extract
from backend.validate import validate

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "mediparse.db"
UPLOADS = ROOT / "data" / "uploads"
MAX_BYTES = 20 * 1024 * 1024
TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}

app = FastAPI(title="MediParse")
# the dashboard may be served from another port during development
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY, filename TEXT, stored_as TEXT, mime_type TEXT,
            status TEXT, data TEXT, issues TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        -- every human fix is kept: future fine-tuning data
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY, bill_id INTEGER REFERENCES bills(id), field TEXT,
            ai_value TEXT, corrected_value TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    return conn


def load(conn, bill_id):
    row = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Bill not found")
    return row


def as_json(row):
    return {"id": row["id"], "filename": row["filename"], "status": row["status"],
            "created_at": row["created_at"], "data": json.loads(row["data"]),
            "issues": json.loads(row["issues"])}


@app.post("/upload")
async def upload(file: UploadFile):
    if file.content_type not in TYPES:
        raise HTTPException(415, "Upload a JPG, PNG, WEBP or PDF")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB")
    try:
        doc = extract(data, file.content_type)
    except Exception as e:  # missing key, rate limit, network, bad model output
        raise HTTPException(502, f"Extraction failed: {e}")
    issues = validate(doc)

    # store under a hash name: the user's filename never touches the filesystem
    stored_as = hashlib.sha256(data).hexdigest()[:16] + TYPES[file.content_type]
    UPLOADS.mkdir(parents=True, exist_ok=True)
    (UPLOADS / stored_as).write_bytes(data)

    with db() as conn:
        cur = conn.execute(
            "INSERT INTO bills (filename, stored_as, mime_type, status, data, issues) VALUES (?, ?, ?, ?, ?, ?)",
            (file.filename, stored_as, file.content_type, "review" if issues else "approved",
             json.dumps(doc), json.dumps(issues)))
        return as_json(load(conn, cur.lastrowid))


@app.get("/bills")
def bills(status: str | None = None):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM bills WHERE ? IS NULL OR status = ? ORDER BY id DESC", (status, status)).fetchall()
    out = []
    for r in rows:
        f = json.loads(r["data"])["fields"]
        out.append({"id": r["id"], "filename": r["filename"], "status": r["status"],
                    "created_at": r["created_at"], "issue_count": len(json.loads(r["issues"])),
                    "patient_name": f["patient_name"]["value"], "hospital_name": f["hospital_name"]["value"],
                    "total": f["total"]["value"]})
    return out


@app.get("/bills/{bill_id}")
def bill(bill_id: int):
    with db() as conn:
        return as_json(load(conn, bill_id))


@app.get("/bills/{bill_id}/file")
def bill_file(bill_id: int):
    with db() as conn:
        row = load(conn, bill_id)
    return FileResponse(UPLOADS / row["stored_as"], media_type=row["mime_type"])


class Correction(BaseModel):
    field: str  # "total" or "line_items.2.amount"
    value: str


@app.patch("/bills/{bill_id}")
def correct(bill_id: int, fix: Correction):
    with db() as conn:
        doc = json.loads(load(conn, bill_id)["data"])
        parts = fix.field.split(".")
        if len(parts) == 1 and parts[0] in FIELDS:
            target, key = doc["fields"][parts[0]], "value"
        elif (len(parts) == 3 and parts[0] == "line_items" and parts[1].isdigit()
              and int(parts[1]) < len(doc["line_items"]) and parts[2] in ("description", "qty", "rate", "amount")):
            target, key = doc["line_items"][int(parts[1])], parts[2]
        else:
            raise HTTPException(422, f"Unknown field '{fix.field}'")
        conn.execute("INSERT INTO corrections (bill_id, field, ai_value, corrected_value) VALUES (?, ?, ?, ?)",
                     (bill_id, fix.field, target[key], fix.value))
        target[key], target["confidence"] = fix.value, 1.0  # a human checked it
        issues = validate(doc)
        conn.execute("UPDATE bills SET data = ?, issues = ?, status = ? WHERE id = ?",
                     (json.dumps(doc), json.dumps(issues), "review" if issues else "approved", bill_id))
        return as_json(load(conn, bill_id))


@app.post("/bills/{bill_id}/approve")
def approve(bill_id: int):
    """Reviewer accepts the bill as is (e.g. a real duplicate charge)."""
    with db() as conn:
        load(conn, bill_id)
        conn.execute("UPDATE bills SET status = 'approved' WHERE id = ?", (bill_id,))
        return as_json(load(conn, bill_id))


@app.get("/export")
def export(format: str = "xlsx"):
    with db() as conn:
        rows = conn.execute("SELECT * FROM bills ORDER BY id").fetchall()
    docs = [as_json(r) for r in rows]
    if format == "json":
        return docs

    bill_header = ["bill_id", "file", "status", "document_type", *FIELDS]
    bill_rows = [[d["id"], d["filename"], d["status"], d["data"]["document_type"],
                  *(d["data"]["fields"][f]["value"] for f in FIELDS)] for d in docs]
    if format == "csv":
        buf = io.StringIO()
        csv.writer(buf).writerows([bill_header, *bill_rows])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=mediparse_bills.csv"})
    if format != "xlsx":
        raise HTTPException(422, "format must be xlsx, csv or json")

    wb = Workbook()
    ws = wb.active
    ws.title = "Bills"
    for r in [bill_header, *bill_rows]:
        ws.append(r)
    items = wb.create_sheet("Line items")
    items.append(["bill_id", "description", "qty", "rate", "amount"])
    for d in docs:
        for i in d["data"]["line_items"]:
            items.append([d["id"], i["description"], i["qty"], i["rate"], i["amount"]])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=mediparse_export.xlsx"})
