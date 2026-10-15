# Handoff for a Claude Code session on the laptop (D:\24H)

Paste into Claude Code opened in `D:\24H`:

```
Read LOCAL_HANDOFF.md, DEMO.md and README.md, then do the steps in LOCAL_HANDOFF.md one by one. Report results in short messages.
```

## Context (as of Oct 15, ~10 PM)
Hayara.ai, INNOHACKS 2.0, AI Automation #3 (hospital bill & insurance reader). FastAPI + SQLite + HTML dashboard.
Branch `claude/funny-einstein-1mlbjh`. Gemini free quota (20/day) is used up, so the team is going **fully local**:
`backend/ocr_extract.py` (Tesseract OCR + label rules) is the extractor; `EXTRACTOR=local` skips Gemini.
MVP works locally: 121/124 fields on the 9 demo documents, every planted mistake caught (see DEMO.md).

New: a **trained** local field finder. `scripts/train_fields.py` OCRs labelled receipts once (cache `data/ocr_cache`),
labels each OCR line with the field whose correct value it contains, trains TF-IDF char n-grams + logistic regression
(CPU, minutes), and compares on 20% held-out documents per field: rules only / model fills gaps / model overrides.
It saves the best choice per field with the model to `data/model/fields.joblib`; `ocr_extract.parse` then uses it.
Approved bills in `hayara.db` are added as training data, so the app learns from its reviewers.

## Rules
- Do NOT call the Gemini API (quota). Run the server with `$env:EXTRACTOR="local"`.
- Never commit API keys, `.env`, `hayara.db`, `data/cache/`, `data/ocr_cache/` or imported dataset images.
- Keep the architecture; small changes; run `python -m pytest -q` after each change.

## Steps
1. `git pull`, `pip install -r requirements.txt` (adds scikit-learn), `python -m pytest -q` (26 should pass).
2. Make sure SROIE is imported: `python scripts/import_dataset.py sroie "D:\datasets\datasets\SROIE\archive\SROIE2019" --limit 600`
   (more data = better model; ~600 receipts OCR in roughly 10-20 min the first time, cached after).
3. Train: `python scripts/train_fields.py`. Report the per-field table and the held-out accuracy line
   ("rules only X% -> with trained model Y%"). Save that output into EVAL_RESULTS.md under a "Trained local model" heading.
4. If the model wins on any field, check the 9 demo documents still behave (DEMO.md table: 4 approved incl. claim_01,
   planted mistakes caught): start the server in local mode, `del hayara.db`, upload data/samples/*.
   If a demo document regresses, set that field's mode back to "rules" (or retrain without that field) — the demo comes first.
5. Commit the code fixes, `EVAL_RESULTS.md` and `data/model/fields.joblib` (the trained model, a few MB) and push.
6. Slide line (only if the numbers support it): "Our own model, trained on N receipts: held-out field accuracy X% -> Y%;
   it retrains from every bill a reviewer approves."
