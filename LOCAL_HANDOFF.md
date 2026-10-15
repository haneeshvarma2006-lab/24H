# Handoff for a Claude Code session running on the laptop

Paste this into Claude Code opened in the `24H` folder on the laptop:

```
Read LOCAL_HANDOFF.md and README.md, then do the steps in LOCAL_HANDOFF.md one by one and report the results.
```

## Context
Hayara.ai (INNOHACKS 2.0, AI Automation #3: hospital bill & insurance reader). Backend: FastAPI + Gemini + Tesseract,
dashboard at http://127.0.0.1:8000/. Branch: `claude/funny-einstein-1mlbjh`. GEMINI_API_KEY and Tesseract are set up on this laptop.
The cloud session could not reach this laptop, so nothing below has run against real Gemini yet.

## Steps
1. `git pull` and `pip install -r requirements.txt`. Run `python -m pytest -q` (should all pass; Tesseract tests skip if it's missing).
2. Smoke test real extraction (the main risk): start `uvicorn backend.app:app --reload`, upload `data/samples/bill_02.png`
   in the dashboard (or `curl -H "X-Hayara: 1" -F "file=@data/samples/bill_02.png;type=image/png" http://127.0.0.1:8000/upload`).
   Expected: status "review" with a total_math issue ("…but total says ₹6,530").
   - "model not found": set `GEMINI_MODEL` to a vision model listed in Google AI Studio and retry.
   - Schema/400 errors from Gemini: fix `backend/extract.py` (keep the output shape `{document_type, fields{name:{value,confidence}}, line_items[]}`), rerun tests.
3. Look at `D:\datasets`: find the CORD and SROIE folders (images + label .json/.txt). Then:
   ```
   python scripts/import_dataset.py cord  "D:\datasets\<cord folder>"  --limit 100
   python scripts/import_dataset.py sroie "D:\datasets\<sroie folder>" --limit 100
   ```
   If it imports 0, inspect the label format and adapt `scripts/import_dataset.py` (CORD: `gt_parse` with menu/sub_total/total;
   SROIE: `{company, date, address, total}`), add a test in `tests/test_mediparse.py`, rerun.
   FUNSD can be skipped (its labels don't map to our fields).
4. `python eval.py --only bill --delay 5` (our 7 demo bills, checks planted mistakes are caught),
   then `python eval.py --only cord --delay 5` and `python eval.py --only sroie --delay 5`. On 429/quota errors use `--delay 10`.
   Save the printed summaries to `EVAL_RESULTS.md` (numbers only, no invented values).
5. Do NOT commit the imported dataset images (`data/samples/cord_*`, `data/samples/sroie_*`, `data/truth/cord_*`, `data/truth/sroie_*`)
   or `data/cache/`. Commit code fixes and `EVAL_RESULTS.md`, push to `claude/funny-einstein-1mlbjh`.
