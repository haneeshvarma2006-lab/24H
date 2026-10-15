# Hayara.ai

AI reads the bill. Math checks the AI. A human approves only what's uncertain.
INNOHACKS 2.0 · AI Automation #3 (Hospital Bill and Insurance Reader). Plan: [PLAN.md](PLAN.md).

## Run

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...        # Windows: setx GEMINI_API_KEY "..." then open a new terminal
uvicorn backend.app:app --reload
```
Open **http://127.0.0.1:8000/** for the dashboard (http://127.0.0.1:8000/docs lists every API endpoint).
Click-to-source highlights need Tesseract on the PATH (`tesseract --version`); without it everything else still works.

```bash
python -m pytest                  # validation rules, click-to-source, API flow, eval scoring; no API key needed
python eval.py --delay 5          # real accuracy on data/samples vs data/truth (1 Gemini call per bill)
python scripts/make_demo_bills.py # regenerate the fictitious demo bills + their correct values
```

Demo bills in `data/samples/` (all fictitious): `bill_01` clean, `bill_02` wrong total, `bill_03` missing patient name +
duplicated medicine, `bill_04` clean pharmacy bill, `bill_05_photo` tilted/blurred phone photo of bill_01.

## API (for the dashboard)

| Endpoint | What it does |
|---|---|
| `POST /upload` (form field `file`) | Extract + validate a JPG/PNG/WEBP/PDF. Returns `{id, status, data, issues}` |
| `GET /bills?status=review` | List bills (`review` or `approved`, or all) |
| `GET /bills/{id}` | One bill: `data.fields`, `data.line_items`, `issues` |
| `GET /bills/{id}/file` | The original scan, for the side-by-side viewer |
| `PATCH /bills/{id}` `{"field": "total", "value": "3450"}` | Human fix (also `line_items.2.amount`). Re-validates; saved as a correction |
| `POST /bills/{id}/approve` | Reviewer accepts the bill as is |
| `GET /export?format=xlsx\|csv\|json` | Spreadsheet-ready export |

Every issue is `{"field", "rule", "message"}`; `field` matches a key in `data.fields` or `line_items.N`, so the UI can highlight it.
Rules: `required`, `line_math`, `duplicate`, `items_sum`, `total_math`, `low_confidence`.

Extraction results are cached in `data/cache/` by file hash, so bills processed once still work with no internet.
