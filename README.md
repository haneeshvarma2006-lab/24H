# MediParse

AI reads the bill. Math checks the AI. A human approves only what's uncertain.
INNOHACKS 2.0 · AI Automation #3 (Hospital Bill and Insurance Reader). Plan: [PLAN.md](PLAN.md).

## Run

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...        # Windows: setx GEMINI_API_KEY "..." then open a new terminal
uvicorn backend.app:app --reload
```
Open http://127.0.0.1:8000/docs to upload a bill and try every endpoint.

```bash
python -m pytest                  # validation rules + API flow, no API key needed
```

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
