"""Hayara.ai API + dashboard. Run from the repo root:  uvicorn backend.app:app --reload
Dashboard: http://127.0.0.1:8000/
"""
import base64
import contextvars
import csv
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from PIL import Image
from pydantic import BaseModel, Field

from backend.extract import FIELDS, extract
from backend.locate import first_page_png, locate
from backend.ocr_extract import ocr_extract
from backend.validate import amount, cross_check, validate

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "hayara.db"
UPLOADS = ROOT / "data" / "uploads"
MAX_BYTES = 20 * 1024 * 1024
TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
Image.MAX_IMAGE_PIXELS = 30_000_000  # PIL refuses images over 2x this: decompression bombs can't eat the server's RAM
MAX_BILLS = 500                      # public demo on a small free disk
UPLOADS_PER_WINDOW, WINDOW_SECONDS = 40, 600
READERS = threading.BoundedSemaphore(1)  # OCR is CPU- and RAM-heavy (3 Tesseract passes each): one at a time fits a 512 MB free instance
recent_uploads = defaultdict(deque)

# docs pages off: no public map of the API
app = FastAPI(title="Hayara.ai", docs_url=None, redoc_url=None, openapi_url=None)

# the dashboard's one inline script is allowed by its hash, so an injected <script> or onerror= never runs
_scripts = [m for page in ("index.html", "login.html")
            for m in re.findall(r"<script>(.*?)</script>", (ROOT / "frontend" / page).read_text(encoding="utf-8"), re.S)]
CSP = ("default-src 'self'; script-src " + " ".join(f"'sha256-{base64.b64encode(hashlib.sha256(x.encode()).digest()).decode()}'" for x in _scripts) + "; "
       "style-src 'self' 'unsafe-inline'; font-src 'self'; "
       "img-src 'self' data: blob:; frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; connect-src 'self'")
HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN", "Referrer-Policy": "no-referrer",
           "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
           "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin",
           "Strict-Transport-Security": "max-age=31536000"}


USER = contextvars.ContextVar("user")  # id of the signed-in user for this request
PUBLIC = {"/health", "/login.html", "/auth/login", "/auth/signup"}
SESSION_DAYS = 7


def session_user(token: str | None):
    if not token:
        return None
    with db() as conn:
        row = conn.execute("SELECT user_id FROM sessions WHERE token = ? AND expires > ?",
                           (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
    return row[0] if row else None


@app.middleware("http")
async def require_header(request: Request, call_next):
    # other websites can still fire simple cross-site POSTs; a custom header forces a CORS preflight they fail
    if request.method in ("POST", "PATCH") and request.headers.get("x-hayara") != "1":
        return Response("Missing X-Hayara header", status_code=403)
    if request.url.path not in PUBLIC and not re.fullmatch(r"/fonts/[\w-]+\.woff2", request.url.path):
        uid = session_user(request.cookies.get("hayara_session"))
        if uid is None:  # every page and API call needs a signed-in user
            if request.method == "GET" and request.url.path in ("/", "/index.html"):
                response = RedirectResponse("/login.html", 303)
            else:
                response = Response('{"detail":"Please sign in"}', 401, media_type="application/json")
            response.headers.update(HEADERS)
            return response
        USER.set(uid)
    response = await call_next(request)
    response.headers.update(HEADERS)
    response.headers["Cache-Control"] = "no-store"  # signed-in pages and bill data never come back from a cache after sign-out
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Content-Security-Policy"] = CSP
    return response


def rate_limit(ip: str):
    """At most UPLOADS_PER_WINDOW uploads per IP per WINDOW_SECONDS (in memory: resets on restart)."""
    now, hits = time.monotonic(), recent_uploads[ip]
    while hits and hits[0] < now - WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= UPLOADS_PER_WINDOW:
        raise HTTPException(429, "Too many uploads from your network. Please wait a few minutes.")
    hits.append(now)


def real_file(data: bytes, mime: str):
    """The browser's type label is user input: the bytes must really be that kind of file."""
    try:
        if mime == "application/pdf":
            import pypdfium2
            ok = b"%PDF-" in data[:1024] and len(pypdfium2.PdfDocument(data)) > 0
        else:
            with Image.open(io.BytesIO(data)) as im:
                ok = im.format == FORMATS[mime]
    except Exception:  # corrupt, truncated, decompression bomb
        ok = False
    if not ok:
        raise HTTPException(415, "This file is damaged or is not really a JPG, PNG, WEBP or PDF")


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY, filename TEXT, stored_as TEXT, mime_type TEXT,
            status TEXT, data TEXT, issues TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, email TEXT UNIQUE, pw_hash TEXT, salt TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
        -- every human fix is kept: future fine-tuning data
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY, bill_id INTEGER REFERENCES bills(id), field TEXT,
            ai_value TEXT, corrected_value TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    try:  # databases from before accounts existed
        conn.execute("ALTER TABLE bills ADD COLUMN user_id INTEGER")
    except sqlite3.OperationalError:
        pass
    return conn


def load(conn, bill_id):
    row = conn.execute("SELECT * FROM bills WHERE id = ? AND user_id = ?", (bill_id, USER.get())).fetchone()
    if row is None:
        raise HTTPException(404, "Bill not found")
    return row


def check(conn, doc):
    """All rule checks; a claim form is also compared with the uploaded bills."""
    issues = validate(doc)
    if doc.get("document_type") == "claim_form":
        # shortcut: a claim is checked when uploaded or edited, not again when its bill is fixed later
        bills = [(r["id"], json.loads(r["data"])) for r in conn.execute("SELECT id, data FROM bills WHERE user_id = ? ORDER BY id DESC", (USER.get(),))]
        issues += cross_check(doc, [(i, d) for i, d in bills if d.get("document_type") == "bill"])
    return issues


def as_json(row):
    return {"id": row["id"], "filename": row["filename"], "mime_type": row["mime_type"], "status": row["status"],
            "created_at": row["created_at"], "data": json.loads(row["data"]),
            "issues": json.loads(row["issues"])}


# plain def: FastAPI runs it in a thread, so slow Gemini/Tesseract calls don't freeze other requests
class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)


login_attempts = defaultdict(deque)


def hash_password(password: str, salt: str) -> str:
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1).hex()


def start_session(request: Request, user_id: int) -> Response:
    token = secrets.token_urlsafe(32)
    with db() as conn:  # only the token's hash is stored: a leaked database can't be used to sign in
        conn.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                     (hashlib.sha256(token.encode()).hexdigest(), user_id, time.time() + SESSION_DAYS * 86400))
    response = Response('{"ok":true}', media_type="application/json")
    response.set_cookie("hayara_session", token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https")
    return response


def throttle_login(request: Request):
    """10 sign-in attempts per IP per 10 minutes: password guessing stays slow."""
    ip = request.client.host if request.client else "?"
    now, hits = time.monotonic(), login_attempts[ip]
    while hits and hits[0] < now - 600:
        hits.popleft()
    if len(hits) >= 10:
        raise HTTPException(429, "Too many sign-in attempts. Wait 10 minutes.")
    hits.append(now)


@app.post("/auth/signup")
def signup(creds: Credentials, request: Request):
    throttle_login(request)
    salt = secrets.token_hex(16)
    try:
        with db() as conn:
            uid = conn.execute("INSERT INTO users (email, pw_hash, salt) VALUES (?, ?, ?)",
                               (creds.email.lower(), hash_password(creds.password, salt), salt)).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    return start_session(request, uid)


@app.post("/auth/login")
def login(creds: Credentials, request: Request):
    throttle_login(request)
    with db() as conn:
        row = conn.execute("SELECT id, pw_hash, salt FROM users WHERE email = ?", (creds.email.lower(),)).fetchone()
    # same work and same answer whether or not the email exists
    check_hash = hash_password(creds.password, row["salt"] if row else "00" * 16)
    if not row or not secrets.compare_digest(check_hash, row["pw_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return start_session(request, row["id"])


@app.post("/auth/logout")
def logout(request: Request):
    with db() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?",
                     (hashlib.sha256(request.cookies.get("hayara_session", "").encode()).hexdigest(),))
    response = Response('{"ok":true}', media_type="application/json")
    response.delete_cookie("hayara_session")
    return response


@app.get("/auth/me")
def me():
    with db() as conn:
        return {"email": conn.execute("SELECT email FROM users WHERE id = ?", (USER.get(),)).fetchone()[0]}


@app.get("/health")
def health():
    return {"ok": True}


SAMPLES = ROOT / "data" / "samples"
DEMO_CACHE = ROOT / "data" / "demo_cache"  # scripts/precompute_demo.py
SAMPLE_RE = re.compile(r"(bill|claim)_\w+\.(png|jpg|pdf)")  # only our fictitious demo documents, never imported datasets


@app.get("/samples")
def samples():
    """Demo documents the dashboard can load in one click (uploads are wiped when the free server restarts)."""
    return sorted(p.name for p in SAMPLES.glob("*") if SAMPLE_RE.fullmatch(p.name))


@app.get("/samples/{name}")
def sample(name: str):
    if not SAMPLE_RE.fullmatch(name) or not (SAMPLES / name).is_file():
        raise HTTPException(404, "No such demo document")
    return FileResponse(SAMPLES / name)


@app.post("/upload")
def upload(file: UploadFile, request: Request):
    rate_limit(request.client.host if request.client else "?")
    if file.content_type not in TYPES:
        raise HTTPException(415, "Upload a JPG, PNG, WEBP or PDF")
    if (file.size or 0) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB")
    real_file(data, file.content_type)
    with db() as conn:
        if conn.execute("SELECT COUNT(*) FROM bills WHERE user_id = ?", (USER.get(),)).fetchone()[0] >= MAX_BILLS:
            raise HTTPException(507, "Storage for this demo is full")
    if not READERS.acquire(timeout=120):
        raise HTTPException(503, "Server is busy reading other bills. Try again in a minute.")
    try:
        return read_and_store(data, file.content_type, (file.filename or "upload")[:200])
    finally:
        READERS.release()


def read(data: bytes, content_type: str) -> tuple[dict, bytes | None]:
    """Extract fields, then find where each was printed. Returns (doc, page-1 PNG for PDFs)."""
    # EXTRACTOR=local skips the AI entirely; otherwise Gemini, with local OCR when it is unavailable
    local, doc, ai_error = os.environ.get("EXTRACTOR") == "local", None, None
    if not local:
        try:
            doc, engine = extract(data, content_type), "Gemini"
        except Exception as e:  # missing key, quota (429), network, bad model output
            ai_error = e
    if doc is None:
        try:
            if not shutil.which("tesseract"):
                raise RuntimeError("Tesseract is not installed")
            doc, engine = ocr_extract(data, content_type), "local OCR"
        except Exception as e:
            if getattr(ai_error, "code", None) == 429:
                raise HTTPException(429, "Gemini free quota is used up for today. Bills already read still open; "
                                         "try again later or switch model.")
            raise HTTPException(502, f"Extraction failed: {ai_error or e}")
    doc["engine"] = engine

    doc["sources"], doc["preview"], preview = {}, False, None
    try:  # highlights are a nice-to-have; never fail an upload over them
        image = data
        if content_type == "application/pdf":
            # shortcut: highlights cover page 1 only; render more pages if multi-page bills matter
            image = preview = first_page_png(data)
            doc["preview"] = True
        if shutil.which("tesseract"):
            doc["sources"] = locate(image, doc)
    except Exception:
        pass
    return doc, preview


def read_and_store(data: bytes, content_type: str, filename: str):
    key = hashlib.sha256(data).hexdigest()
    demo = DEMO_CACHE / f"{key}.json"
    if demo.exists():  # one of our 9 demo documents: the engine's saved output, instant on a slow free server
        doc = json.loads(demo.read_text())
        preview = first_page_png(data) if doc.get("preview") else None
    else:
        doc, preview = read(data, content_type)
    # store under a hash name: the user's filename never touches the filesystem
    stored_as = key[:16] + TYPES[content_type]
    UPLOADS.mkdir(parents=True, exist_ok=True)
    (UPLOADS / stored_as).write_bytes(data)
    if preview:
        (UPLOADS / (stored_as + ".png")).write_bytes(preview)

    with db() as conn:
        issues = check(conn, doc)
        cur = conn.execute(
            "INSERT INTO bills (user_id, filename, stored_as, mime_type, status, data, issues) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (USER.get(), filename, stored_as, content_type, "review" if issues else "approved",
             json.dumps(doc), json.dumps(issues)))
        return as_json(load(conn, cur.lastrowid))


@app.get("/bills")
def bills(status: str | None = None):
    with db() as conn:
        rows = conn.execute(
            "SELECT *, (SELECT COUNT(*) FROM corrections c WHERE c.bill_id = bills.id) AS fixes FROM bills "
            "WHERE user_id = ? AND (? IS NULL OR status = ?) ORDER BY id DESC", (USER.get(), status, status)).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        f = d["fields"]
        out.append({"id": r["id"], "filename": r["filename"], "status": r["status"], "document_type": d["document_type"],
                    "created_at": r["created_at"], "issue_count": len(json.loads(r["issues"])), "fixes": r["fixes"],
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


@app.get("/bills/{bill_id}/preview")
def bill_preview(bill_id: int):
    """Page 1 of a PDF as an image, so the dashboard can draw highlights on it."""
    with db() as conn:
        row = load(conn, bill_id)
    path = UPLOADS / (row["stored_as"] + ".png")
    if not path.exists():
        raise HTTPException(404, "No preview for this upload")
    return FileResponse(path, media_type="image/png")


class Correction(BaseModel):
    field: str = Field(max_length=40)  # "total" or "line_items.2.amount"
    value: str = Field(max_length=500)


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
        conn.execute("UPDATE bills SET data = ?, issues = ?, status = ? WHERE id = ? AND user_id = ?",
                     (json.dumps(doc), json.dumps(issues), "approved" if kept or not issues else "review", bill_id, USER.get()))
        return as_json(load(conn, bill_id))


@app.post("/bills/{bill_id}/approve")
def approve(bill_id: int):
    """Reviewer accepts the bill as is (e.g. a real duplicate charge)."""
    with db() as conn:
        load(conn, bill_id)
        conn.execute("UPDATE bills SET status = 'approved' WHERE id = ? AND user_id = ?", (bill_id, USER.get()))
        return as_json(load(conn, bill_id))


@app.get("/export")
def export(format: str = "xlsx"):
    with db() as conn:
        rows = conn.execute("SELECT * FROM bills WHERE user_id = ? ORDER BY id", (USER.get(),)).fetchall()
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
