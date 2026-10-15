# Hayara.ai — final demo kit (INNOHACKS 2.0, AI Automation #3)

## Before going on stage (5 min)
```
cd D:\24H
git pull
del hayara.db                      # start with an empty dashboard
$env:EXTRACTOR="local"             # fully offline; remove this line to try Gemini first (falls back to local by itself)
python -m uvicorn backend.app:app --port 8001
```
Open http://127.0.0.1:8001/ . Keep `D:\24H\data\samples` open in Explorer. Charger plugged in, laptop on "never sleep".

## Results (real measurements — only these numbers on slides)
| Engine | What was measured | Result |
|---|---|---|
| Gemini 3.8 Flash (cloud AI) | 6 demo bills, fresh calls (`EVAL_RESULTS.md`) | **82/85 fields (96.5%)**, **28/28 line items**, **6/6 correct verdicts** |
| Local mode (Tesseract OCR + rules, no internet) | all 9 demo documents | **121/124 fields (97.6%)**, 28/33 line items (blurry photo's table unread → sent to review) |
| Our trained field finder (local, CPU) | 600 SROIE receipts, 20% held out | held-out field accuracy **21.0% → 28.8%** vs rules alone (shop receipts, a much harder layout than our bills) |
| Validation | 4 documents with planted mistakes | **4/4 caught**: wrong total, missing name + duplicate medicine, qty×rate error, over-claim |
| Validation | 4 clean documents | **4/4 auto-approved** |

Honest limits: Gemini and local-mode numbers come from our 9 demo documents (the free Gemini tier allows 20 calls/day, so Gemini was not benchmarked on SROIE); the trained-model numbers come from SROIE shop receipts, not hospital bills.

## Results slide text
**Title:** Results
- Cloud AI read **96.5%** of fields correctly, every line item right
- Fully offline mode: **97.6%** of fields, no internet, no API cost
- **Every planted mistake caught**: wrong total, duplicate medicine, qty × rate error, over-claimed insurance
- Clean bills **auto-approved**; only uncertain ones reach a human
- Works on scans, phone photos and PDFs

## 3-minute live demo
1. **Click "▶ Try the demo bills"** on the start page (or Ctrl+A in data/samples and drop them). Loads in seconds: for these 9 the engine's output is saved (the free server has ~0.1 CPU). To show live reading, upload any other bill or a phone photo (~30-60 s on Render, ~3 s on the laptop). *"Any hospital, any layout: scan, phone photo, PDF."*
2. **bill_01 → Approved, trust ring 100%.** Hover fields: *"Click-to-source: every value is shown where it was read."* Point at the top: *"Read → Math checked → Verified → Export. 'No human needed' shows how much we automate."*
3. **bill_02 → wrong total.** *"The bill says ₹6,530, the items add up to ₹5,730. The AI read it right; the math caught the hospital's mistake."* Click the issue → type 5730 → Enter → Approved → **Review next →** jumps to the next bill in the queue.
4. **bill_03 →** missing patient name + same medicine billed twice.
5. **bill_06 →** *"HbA1c: 2 × 400 = 800, bill says 900."*
6. **claim_02 →** *"The insurance claim asks ₹6,530 but the matching bill supports ₹5,730. We protect the insurer from over-claims."*
7. **Excel export.** *"Clean, verified data ready for any hospital or TPA system."*
8. Close: *"AI reads the bill. Math checks the AI. A human approves only what's uncertain."*

## Judge Q&A
- **Did you train a model?** Yes, a small one, on purpose. Our own field finder (TF-IDF + logistic regression on OCR lines) trained on 600 SROIE receipts on a laptop CPU: held-out field accuracy rose from 21% to 29% over rules alone. It only takes over a field where it measured better, and it retrains from every bill a reviewer approves. The heavy reading is done by a pretrained vision AI when available, or locally by OCR.
- **What if the AI is wrong?** Every number is checked by rules (totals, tax, qty × rate, duplicates, claim vs bill). Low-confidence fields go to a human. Nothing wrong is exported silently.
- **What if the internet or the AI quota fails?** It switches to fully local OCR automatically. You're watching that mode now.
- **Privacy?** Local mode never sends the bill anywhere. Demo data is fictitious.
- **Was the demo precomputed?** For the 9 sample documents, yes: the hosted free server is very slow, so the engine's own output for them is saved (`scripts/precompute_demo.py`, page says "precomputed demo"). Any new upload is read live; try a photo of any bill.
- **Is it just a ChatGPT wrapper?** The AI only reads. Validation, click-to-source, claim cross-check, review queue and export are ours, and it runs with no AI at all.
- **What's next?** Overcharge alerts vs government rates (CGHS/NPPA), regional-language bills, an API for hospitals and insurers. Every human correction is saved as training data for a fine-tuned model later.
