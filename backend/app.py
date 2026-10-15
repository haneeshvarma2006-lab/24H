"""Hayara.ai API + dashboard. Run from the repo root:  uvicorn backend.app:app --reload
Dashboard: http://127.0.0.1:8000/   API test page: http://127.0.0.1:8000/docs
"""
import base64
import csv
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from pydantic import BaseModel

from backend.extract import FIELDS, extract
from backend.locate import locate
from backend.validate import amount, cross_check, validate

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "hayara.db"
UPLOADS = ROOT / "data" / "uploads"
MAX_BYTES = 20 * 1024 * 1024
TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}

app = FastAPI(title="Hayara.ai")


@app.middleware("http")
async def require_password(request: Request, call_next):
    """When hosted, one shared password (APP_PASSWORD) keeps strangers from spending the Gemini quota."""
    password = os.environ.get("APP_PASSWORD")
    if password:
        try:
            given = base64.b64decode(request.headers.get("authorization", "").removeprefix("Basic ")).partition(b":")[2]
        except ValueError:
            given = b""
        if not secrets.compare_digest(given, password.encode()):
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Hayara.ai"'})
    # other websites can still fire simple cross-site POSTs; a custom header forces a CORS preflight they fail
    if request.method in ("POST", "PATCH") and request.headers.get("x-hayara") != "1":
        return Response("Missing X-Hayara header", status_code=403)
    return await call_next(request)


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


def check(conn, doc):
    """All rule checks; a claim form is also compared with the uploaded bills."""
    issues = validate(doc)
    if doc.get("document_type") == "claim_form":
        # shortcut: a claim is checked when uploaded or edited, not again when its bill is fixed later
        bills = [(r["id"], json.loads(r["data"])) for r in conn.execute("SELECT id, data FROM bills ORDER BY id DESC")]
        issues += cross_check(doc, [(i, d) for i, d in bills if d.get("document_type") == "bill"])
    return issues


def as_json(row):
    return {"id": row["id"], "filename": row["filename"], "mime_type": row["mime_type"], "status": row["status"],
            "created_at": row["created_at"], "data": json.loads(row["data"]),
            "issues": json.loads(row["issues"])}


# plain def: FastAPI runs it in a thread, so slow Gemini/Tesseract calls don't freeze other requests
@app.post("/upload")
def upload(file: UploadFile):
    if file.content_type not in TYPES:
        raise HTTPException(415, "Upload a JPG, PNG, WEBP or PDF")
    if (file.size or 0) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB")
    data = file.file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB")
    try:
        doc = extract(data, file.content_type)
    except Exception as e:  # missing key, rate limit, network, bad model output
        raise HTTPException(502, f"Extraction failed: {e}")
    doc["sources"] = {}
    # shortcut: click-to-source only for images, PDFs would need page rendering first
    if file.content_type.startswith("image/") and shutil.which("tesseract"):
        try:
            doc["sources"] = locate(data, doc)
        except Exception:
            pass  # highlights are a nice-to-have; never fail an upload over them

    # store under a hash name: the user's filename never touches the filesystem
    stored_as = hashlib.sha256(data).hexdigest()[:16] + TYPES[file.content_type]
    UPLOADS.mkdir(parents=True, exist_ok=True)
    (UPLOADS / stored_as).write_bytes(data)

    with db() as conn:
        issues = check(conn, doc)
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
        d = json.loads(r["data"])
        f = d["fields"]
        out.append({"id": r["id"], "filename": r["filename"], "status": r["status"], "document_type": d["document_type"],
                    "created_at": r["created_at"], "issue_count": len(json.loads(r["issues"])),
                    "patient_name": f["patient_name"]["value"], "hospital_name": f["hospital_name"]["value"],
                    "total": f["total"]["value"] or f["claimed_amount"]["value"]})
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
        row = load(conn, bill_id)
        doc = json.loads(row["data"])
        parts = fix.field.split(".")
        if len(parts) == 1 and parts[0] in FIELDS:
            target, key = doc["fields"][parts[0]], "value"
        elif (len(parts) == 3 and parts[0] == "line_items" and parts[1].isdigit()
              and int(parts[1]) < len(doc["line_items"]) and parts[2] in ("description", "qty", "rate", "amount")):
            target, key = doc["line_items"][int(parts[1])], parts[2]
        else:
            raise HTTPException(422, f"Unknown field '{fix.field}'")
        first = conn.execute("SELECT ai_value FROM corrections WHERE bill_id = ? AND field = ? ORDER BY id LIMIT 1",
                             (bill_id, fix.field)).fetchone()  # keep what the AI said, not a human's earlier edit
        conn.execute("INSERT INTO corrections (bill_id, field, ai_value, corrected_value) VALUES (?, ?, ?, ?)",
                     (bill_id, fix.field, first[0] if first else target[key], fix.value))
        target[key], target["confidence"] = fix.value, 1.0  # a human checked it
        issues = check(conn, doc)
        # a reviewer's approval survives edits unless the edit creates a new problem
        approved_issues = {(i["field"], i["rule"]) for i in json.loads(row["issues"])}
        kept = row["status"] == "approved" and all((i["field"], i["rule"]) in approved_issues for i in issues)
        conn.execute("UPDATE bills SET data = ?, issues = ?, status = ? WHERE id = ?",
                     (json.dumps(doc), json.dumps(issues), "approved" if kept or not issues else "review", bill_id))
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

    def number(v):
        """Amounts go to Excel as numbers so SUM works; anything else stays text."""
        return amount(v) if isinstance(v, str) and re.fullmatch(r"-?[\d,]+(\.\d+)?", v.strip()) else cell(v)

    def cell(v):
        """Text from scans and filenames must stay text: no Excel formulas, no characters that break xlsx."""
        if not isinstance(v, str):
            return v
        v = ILLEGAL_CHARACTERS_RE.sub("", v)
        return "'" + v if v[:1] in ("=", "+", "@", "\t", "\r") else v

    bill_header = ["bill_id", "file", "status", "document_type", *FIELDS]
    bill_rows = [[cell(v) for v in [d["id"], d["filename"], d["status"], d["data"]["document_type"],
                                    *(d["data"]["fields"][f]["value"] for f in FIELDS)]] for d in docs]
    if format == "csv":
        buf = io.StringIO()
        csv.writer(buf).writerows([bill_header, *bill_rows])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=hayara_bills.csv"})
    if format != "xlsx":
        raise HTTPException(422, "format must be xlsx, csv or json")

    wb = Workbook()
    ws = wb.active
    ws.title = "Bills"
    money = {bill_header.index(f) for f in ("subtotal", "discount", "tax", "total", "claimed_amount")}
    ws.append(bill_header)
    for r in bill_rows:
        ws.append([number(v) if i in money else v for i, v in enumerate(r)])
    items = wb.create_sheet("Line items")
    items.append(["bill_id", "description", "qty", "rate", "amount"])
    for d in docs:
        for i in d["data"]["line_items"]:
            items.append([d["id"], cell(i["description"]), *(number(i[c]) for c in ("qty", "rate", "amount"))])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=hayara_export.xlsx"})


# last, so every API route above wins over a file of the same name
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="dashboard")
