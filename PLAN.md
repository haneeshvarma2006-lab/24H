# INNOHACKS 2.0: Hospital Bill & Insurance Reader

**Problem statement:** AI Automation #3, Hospital Bill and Insurance Reader
**Working name:** ClaimLens
**Pitch:** *"AI reads the bill. Math checks the AI. A human approves only what's uncertain."*

---

## 1. What we build

A messy scanned bill or claim form goes in. Clean, verified data comes out: a spreadsheet or database row.

```
Upload (PDF / phone photo)
  -> Extract:   a pretrained vision AI model reads the scan and returns JSON
                (patient, hospital, dates, line items, totals, policy no.)
  -> Validate:  line items sum to subtotal, tax matches the rate, totals match,
                required fields present, confidence per field
  -> Overcharge check: compare items with government reference rates
                (CGHS package rates, NPPA drug ceiling prices)
  -> Route:     all checks pass -> auto-approved
                anything fails or has low confidence -> human review queue
  -> Dashboard: scan on the left, data on the right, click a value to see
                where it was read on the scan
  -> Export:    Excel / CSV / database
```

**We do NOT train a model.** That decision is final. The pretrained model does the reading. Our work is everything around it: validation, review and export. We use datasets to **measure accuracy** (a real number for the slides), not to train.

---

## 2. Repo structure

```
24H/
  backend/
    app.py        FastAPI: POST /upload, GET /bills, GET /bills/{id}, PATCH /bills/{id}, GET /export
    extract.py    sends the scan to the vision AI model, returns JSON in a fixed format
    validate.py   math, tax, missing-field, confidence and overcharge checks
    db.py         SQLite (one file, no setup)
  frontend/
    index.html    upload, review queue, side-by-side viewer, export button
  data/
    samples/      demo bills and claim forms (made up or public, NEVER real patients)
    truth/        hand-checked correct JSON for ~10 demo bills
    public/       subsets of CORD / SROIE / FUNSD for the accuracy check
    rates/        CGHS rate list, NPPA ceiling prices (CSV)
    cache/        saved extraction results, so the demo works with no internet
  tests/
    test_validate.py
  eval.py         runs the extractor on data/public + data/truth, prints accuracy %
```

---

## 3. Datasets: what, how much, where

Teammate: download these and put them in `data/` (or a Google Drive folder and share the link).
**Take subsets only. We need around 100 images per dataset, not the full sets.**

| # | Dataset | What it is | How much we need | Where to find it | Why we need it |
|---|---|---|---|---|---|
| 1 | **CORD v2** | Real receipts with line items, subtotals, tax and totals, all labelled | 100 images + their labels | Hugging Face: `naver-clova-ix/cord-v2` | Measures line-item and total accuracy. Gives the "X% accurate" number for the slides |
| 2 | **SROIE** (ICDAR 2019) | Scanned receipts labelled with company, date, address, total | 100 images + labels | Kaggle: search "SROIE dataset" | Second accuracy check, on low-quality scans |
| 3 | **FUNSD** | Scanned forms with labelled fields | 30 forms | Search "FUNSD dataset" | Accuracy on forms, which is what claim forms are |
| 4 | **Indian hospital bill samples** | Bill images from many hospitals | 15–20 images, **different layouts** | Google Images: "hospital bill format India", "hospital bill sample", "pharmacy bill India" | Demo material. Shows we handle any hospital's format |
| 5 | **IRDAI standard health claim form** | Official blank reimbursement claim form (Part A + Part B) | 1 PDF; fill 5 copies with **made-up** data | Any Indian health insurer's website, or search "IRDAI claim form Part A Part B" | Demo for the bill vs claim form cross-check |
| 6 | **CGHS rate list** | Government reference prices for procedures and tests | The full list (PDF or Excel) | cghs.gov.in, search "CGHS rate list" | Overcharge check: "charged ₹2,500, CGHS rate ₹1,100" |
| 7 | **NPPA ceiling prices** | Legal maximum prices for scheduled medicines | The full list | nppaindia.nic.in, search "NPPA ceiling price list" | Overcharge check on medicines |
| 8 | **Phone photos** | 5–10 printed bills photographed at an angle or crumpled | 10 photos | Print 5 sample bills and photograph them | Realistic messy input for the demo |

Rules for the teammate:
- **No real patient data, ever.** Use made-up names and numbers only.
- Name files simply: `bill_01.jpg`, `claim_01.pdf`.
- For **5 of the demo bills**, write the correct values in a sheet (patient name, date, every line item, subtotal, tax, total). That sheet is our ground truth.
- Put **2–3 deliberate mistakes** in some demo bills (a wrong total, a missing field, an overpriced medicine). The demo shows us catching them.

---

## 4. Team roles

| Who | Owns |
|---|---|
| You (lead) + Claude | `extract.py`, `validate.py`, `eval.py`, backend API |
| Teammate 2 | Datasets (section 3), ground-truth sheet, testing every sample bill |
| Teammate 3 (if any) | Frontend dashboard |
| Brother | Presentation, demo script, judges' Q&A (section 6) |

---

## 5. Timeline (24h, hard gates)

| Hour | Goal | Gate |
|---|---|---|
| 0–1 | API key ready, datasets started downloading, output format fixed | Nobody waits on downloads: start coding with 3 sample bills from Google |
| 1–6 | One bill goes all the way: upload -> extract -> validate -> saved | **Hour 6: must work end to end, even if it looks ugly** |
| 6–12 | All checks + review queue + `eval.py` gives the first accuracy number | Drop whatever isn't working by hour 12 |
| 12–16 | Dashboard: side-by-side viewer, click-to-source, Excel export | |
| 16–18 | Overcharge check (CGHS / NPPA) + bill vs claim form cross-check | Stretch features. Skip them if behind |
| **18** | **FEATURE FREEZE** | After this, only bug fixes |
| 18–21 | Run every sample bill, fix bugs, save results to `data/cache/` | |
| 21–24 | Final slides, rehearse the demo 3 times, record a backup video | |

---

## 6. Presentation (brother)

### Slides (8 slides, about 3 minutes plus a 2-minute live demo)
1. **Hook:** a photo of a messy hospital bill. "Hospital staff in India retype thousands of these by hand every day."
2. **Problem:** every hospital uses a different format, and retyping by hand is slow and error-prone. Patients get overcharged and nobody notices.
3. **Solution:** the pitch line + the 5-step flow (Extract -> Validate -> Overcharge check -> Review -> Export).
4. **Live demo** (see script below).
5. **How it works:** architecture diagram. Make clear that the validation layer is our own work.
6. **Results:** accuracy from `eval.py` (e.g. "X% of fields correct on 200 real receipts"), the processing time per bill, and the share of bills sent to human review.
7. **Impact:** time saved per bill, overcharges caught, works with any hospital format.
8. **Future + team:** connect to insurer systems, support regional languages, run fully on the hospital's own servers for privacy.

### Demo script (2 minutes)
1. Upload a clean bill: green, auto-approved, export to Excel. *(20 s)*
2. Upload a crumpled phone photo: still extracted correctly. *(20 s)*
3. Upload the bill with the **wrong total**: red flag, "Items add up to ₹48,200 but the total says ₹52,000", sent to review. *(30 s)*
4. Click a field: the matching spot on the scan is highlighted. *(15 s)*
5. Overcharged medicine flagged against the NPPA ceiling price. *(20 s)*
6. Fix one field in the review screen, approve, export. *(15 s)*

### Judges' Q&A (prepare these answers)
- **"Did you train a model?"** No, on purpose. We use a pretrained vision model and **measured** it on real receipt datasets: X% accuracy. Our contribution is the verification layer that catches its mistakes.
- **"Isn't this just ChatGPT?"** The AI only reads. The math checks, rate comparisons, confidence routing and review flow are ours. Show the wrong-total demo.
- **"What about patient privacy?"** No real data in the demo. In production, the same pipeline can run on a model hosted inside the hospital.
- **"What if the AI reads something wrong?"** It gets low confidence or fails a math check, so a human sees it. Nothing wrong gets exported silently.

---

## 7. Why we won't fail

| How teams fail | Our fix |
|---|---|
| Training takes forever and the model is bad | No training |
| Nothing works until the last hour | Hour 6 gate |
| Too many half-done features | Hour 18 feature freeze; overcharge check is a stretch feature |
| Wi-Fi or the AI service dies during judging | `data/cache/` replays saved results + backup video |
| "Just a wrapper" | Validation, overcharge check and review queue are ours; accuracy is measured |
| AI misreads on stage | Shows up as low confidence -> review. We demo that on purpose |
