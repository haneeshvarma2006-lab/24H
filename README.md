# Hayara.ai

AI reads the bill. Math checks the AI. A human approves only what's uncertain.
INNOHACKS 2.0 · AI Automation #3 (Hospital Bill and Insurance Reader). Plan: [PLAN.md](PLAN.md).

## Run

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...        # Windows: setx GEMINI_API_KEY "..." then open a new terminal
uvicorn backend.app:app --reload
```
Open **http://127.0.0.1:8000/** for the dashboard.
Click-to-source highlights need Tesseract on the PATH (`tesseract --version`); without it everything else still works.

**No AI quota? Still works.** If Gemini fails (quota used up, no internet, no key), Hayara reads the bill locally
with Tesseract OCR + label rules (`backend/ocr_extract.py`); the dashboard shows "Read by local OCR".
Force fully-local mode: `set EXTRACTOR=local` (PowerShell: `$env:EXTRACTOR="local"`) before starting the server.
Local mode on the 9 demo documents: 121/124 fields correct, clean bills approved, every planted mistake caught. Digital PDFs are read from their text layer; blurry photos go to review.

```bash
python -m pytest                  # validation rules, click-to-source, API flow, eval scoring; no API key needed
python eval.py --delay 5          # real accuracy on data/samples vs data/truth (1 Gemini call per bill)
python scripts/make_demo_bills.py # regenerate the fictitious demo bills + their correct values
```

Demo bills in `data/samples/` (all fictitious): `bill_01` clean, `bill_02` wrong total, `bill_03` missing patient name +
duplicated medicine, `bill_04` clean pharmacy bill, `bill_05_photo` tilted/blurred phone photo of bill_01,
`bill_06` lab invoice with a qty × rate mistake, `bill_07.pdf` clean hospital bill as a PDF (highlights on page 1).
`claim_01` / `claim_02` are insurance claim forms for bill_01 / bill_02. Upload the bills first: claim_01 matches,
claim_02 is flagged ("Claimed ₹6,530, but the matching bill adds up to ₹5,730").

## API (for the dashboard)

| Endpoint | What it does |
|---|---|
| `POST /upload` (form field `file`; every POST/PATCH needs header `X-Hayara: 1`) | Extract + validate a JPG/PNG/WEBP/PDF. Returns `{id, status, data, issues}` |
| `GET /bills?status=review` | List bills (`review` or `approved`, or all) |
| `GET /bills/{id}` | One bill: `data.fields`, `data.line_items`, `issues` |
| `GET /bills/{id}/file` | The original scan, for the side-by-side viewer |
| `PATCH /bills/{id}` `{"field": "total", "value": "3450"}` | Human fix (also `line_items.2.amount`). Re-validates; saved as a correction |
| `POST /bills/{id}/approve` | Reviewer accepts the bill as is |
| `GET /export?format=xlsx\|csv\|json` | Spreadsheet-ready export |
| `GET /samples`, `GET /samples/{name}` | The 9 fictitious demo documents (the start page's "Try the demo bills" button; the engine's output for them is saved in `data/demo_cache/` by `scripts/precompute_demo.py`, every other upload is read live) |
| `GET /health` | `{"ok": true}` for uptime monitors |

Every issue is `{"field", "rule", "message"}`; `field` matches a key in `data.fields` or `line_items.N`, so the UI can highlight it.
Rules: `required`, `line_math`, `duplicate`, `items_sum`, `total_math`, `low_confidence`.

Extraction results are cached in `data/cache/` by file hash, so bills processed once still work with no internet.

## Security

- **Uploads:** only JPG/PNG/WEBP/PDF whose bytes really are that type, max 20 MB; image-bomb and giant-PDF limits;
  files are stored under a hash name, never the user's filename.
- **Abuse limits:** 40 uploads per IP per 10 min, one document read at a time, 500 documents stored.
- **Browser:** Content-Security-Policy (only the dashboard's own script runs, by hash), every value from a scan is
  HTML-escaped, `nosniff`, same-origin framing only, no referrer, HSTS. No CORS: other sites can't read the API.
- **Cross-site writes:** every POST/PATCH needs the `X-Hayara: 1` header, which other websites can't send.
- **Exports:** text that looks like an Excel formula is neutralised (`'=...`).
- **Secrets:** API keys only in environment variables (`.env` is git-ignored); local mode needs no key at all.
- **Accounts:** email + password sign-in; passwords stored as salted scrypt hashes, session tokens stored only as SHA-256 hashes, HttpOnly + SameSite=Strict cookies (Secure on HTTPS), 7-day expiry, sign-out deletes the session, 10 sign-in attempts per IP per 10 min, same answer for unknown email and wrong password.
- **Isolation:** every bill, scan, edit, approval and export is scoped to the signed-in account; other accounts get 404.
- **No caching:** `Cache-Control: no-store`, so nothing is shown from cache after sign-out.
- **Known limits:** the free server keeps accounts in SQLite on a disk that is wiped on restart (sign up again after a restart); no email verification or password reset yet.

## Put it online (free)

The repo has a `Dockerfile` (Python + Tesseract) and a Render blueprint (`render.yaml`).

1. Sign in at **render.com** with GitHub → **New → Blueprint** → pick this repo and branch.
2. When asked, type the secrets into Render (never into the code):
   - `GEMINI_API_KEY`: your Gemini key
3. Wait for the build (~5 min). Your link is `https://hayara-ai-xxxx.onrender.com`.

Free-plan limits: the app sleeps after ~15 min idle (first visit then takes ~1 min to wake, so open it before judging),
and bills uploaded online are wiped when it restarts. That's fine for a demo; production would use PostgreSQL.
