# INNOHACKS 2.0: Hospital Bill & Insurance Reader

**Problem statement:** AI Automation #3, Hospital Bill and Insurance Reader
**Working name:** MediParse
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
    app.py        FastAPI + SQLite: POST /upload, GET /bills, GET /bills/{id}, PATCH /bills/{id}, GET /export
    extract.py    sends the scan to the vision AI model, returns JSON in a fixed format
    validate.py   math, tax, missing-field, confidence and overcharge checks
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

## 5. Timeline (mapped to the official TECHSPARK schedule)

| When (IST) | Official slot | Us | Hard deadline |
|---|---|---|---|
| **Thu 1:00–4:30 PM** | Sprint 1: Problem Statement + PPT | Brother: PPT v1 (slides 1–3, 5, 7, 8; mockup for the demo slide). Coders: API key + `extract.py` working on 3 Google sample bills. Teammate: datasets | **PPT submitted by 5:00 PM** |
| 5:00–7:30 PM | Sprint 2: MVP | `validate.py` + API + SQLite. One bill all the way: upload -> extract -> validate -> saved | |
| 7:30–8:30 PM | Dinner | Eat. Leave `eval.py` running on CORD/SROIE | |
| 8:30–11:30 PM | Sprint 2: MVP | Basic dashboard + review queue + Excel export | **MVP submitted by 11:30 PM** (ugly is fine, broken is not) |
| Fri 12:01–1:30 AM | Networking / relax | Sleep in shifts. Nobody codes tired | |
| 1:30–7:30 AM | Sprint 3: End Application | Click-to-source, confidence routing, first accuracy number, then overcharge check (CGHS/NPPA) + claim cross-check as stretch | |
| **8:30 AM** | Sprint 3 | **FEATURE FREEZE.** Only bug fixes after this. Run every sample bill, save to `data/cache/` | |
| 10:00 AM–1:00 PM | Verification & judge-dashboard prep | Final PPT with real accuracy numbers, record a backup video, rehearse the demo 3 times | **Final code + PPT by 1:00 PM** |
| 4:00–4:30 PM | Evaluation | Present | |

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

---

## 8. Final decisions (merged with the team's plan)

| Topic | Decision | Why |
|---|---|---|
| Extraction | **OCR (Tesseract) + vision AI model** | The AI reads the meaning. OCR gives word positions, which **click-to-source needs** (vision models return unreliable coordinates) |
| Database | **SQLite** for the build, **PostgreSQL** named for production on the slides | No accounts, no network dependency, one file. MVP is due 11:30 PM |
| Frontend | Next.js + Tailwind **only if the frontend owner has shipped Next.js before**; otherwise plain HTML + Tailwind CDN | Ship speed beats stack prestige. UX still matters: polish it in Sprint 3 |
| Export | Excel + CSV + JSON | JSON costs nothing |
| Click-to-source | **Sprint 3 core feature**, not a stretch goal | Biggest demo value |
| Duplicate line-item check | **Add to validation** | Cheap rule, good demo error |
| Overcharge (CGHS/NPPA), bill vs claim cross-check | **Stretch**, after 4:30 AM only if everything else works | Scope control |

### Output schema (lock this now; everyone codes against it)
Flat, so it maps 1:1 to spreadsheet columns. Defined in `backend/extract.py` (`FIELDS`).
```json
{
  "document_type": "bill | claim_form | other",
  "fields": {
    "patient_name": {"value": "Ravi Kumar", "confidence": 0.95},
    "...": "uhid, age, gender, hospital_name, hospital_address, doctor, bill_no, bill_date, admission_date, discharge_date, subtotal, discount, tax, total, insurer, tpa, policy_no, claim_no, claimed_amount"
  },
  "line_items": [{"description": "Room rent", "qty": "2", "rate": "1500", "amount": "3000", "confidence": 0.95}]
}
```

### Validation rules (validate.py)
1. sum(line_items.amount) == subtotal (±1 rupee for rounding)
2. subtotal - discount + tax == total (±1)
3. qty × rate == amount for every line
4. Required fields present: patient.name, hospital.name, bill_date, total
5. No duplicate line items (same description + amount)
6. Any field with confidence < 0.8 → review queue

### Long-term path (answer to "isn't a pretrained API temporary?")
- Every reviewer correction is saved (scan, field, AI value, corrected value) in a `corrections` table. **Build this in the MVP**: it is one table.
- Those corrections become labelled Indian hospital-bill data. Once there are enough, fine-tune a model on them.
- `extract.py` is the only file that knows which model is used, so switching to a self-hosted open-source model for privacy or cost is a one-file change.
