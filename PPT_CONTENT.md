# PPT content: InnoHack 2.0 template (6 slides)

Each heading below is a box in the official template. Paste the text into that box.
Text in [brackets] is for you to fill in.

## Slide 1: Title
- **Project title:** HAYARA.AI
- **Subtitle (optional, under the title):** AI Hospital Bill & Insurance Reader
- **Team name:** [Team name]
- **Team members:** [Member 1, Member 2, Member 3, Member 4]
- **College:** [College name]
- **Problem statement ID:** AI Automation – 3 (Hospital Bill and Insurance Reader)

## Slide 2: Problem statement with problem ID
**Title:** PROBLEM STATEMENT – AI AUTOMATION #3

**Problem box:**
Hospital Bill and Insurance Reader: hospital bills and insurance papers are long, messy and different at every hospital. Staff retype them by hand, which is slow and error-prone.
- Every hospital uses its own layout, so no fixed template works
- Manual retyping causes wrong amounts, missed line items, and rejected or delayed claims
- Plain OCR gives raw text, not clean data, and never says when it is wrong

**Proposed solution box:**
Hayara.ai reads scanned bills and claim forms and returns clean, verified data ready for a spreadsheet or database.
- **Extract:** a pretrained AI vision model pulls patient details, line-item charges, totals and claim data from any format
- **Verify:** our rule engine checks the math (line items = subtotal, tax, grand total) and missing fields, with a confidence score per field
- **Review & export:** only uncertain bills go to a human; one click to Excel, CSV or a database

## Slide 3: Technology stack
- **01 Programming languages:** Python, JavaScript, SQL
- **02 Frontend technologies:** HTML5, CSS, JavaScript; a review dashboard that shows the scan and the extracted data side by side
- **03 Backend technologies:** FastAPI (Python), Pydantic for data validation, pandas / openpyxl for Excel export
- **04 Database and storage:** SQLite (MVP), PostgreSQL (production), local storage for uploaded scans
- **05 AI/ML and APIs** (the template says "A/ML", so fix that typo): a pretrained vision AI model via API ([Claude / Gemini]), with no training needed; CORD, SROIE and FUNSD public datasets used to *measure* accuracy
- **06 Cloud, deployment and dev tools:** Git and GitHub, VS Code, Postman; deploy on Render or Railway, or a local server

## Slide 4: Solution architecture & workflow diagram
Draw 5 boxes left to right, joined by arrows:

```
[1. UPLOAD]  →  [2. AI EXTRACTION]  →  [3. VALIDATION]  --pass-->  [4. AUTO-APPROVED]  →  [5. OUTPUT]
 Scanned bill /   Vision model →          Items = subtotal?            All checks pass,          Excel · CSV ·
 claim form       patient, charges,       Tax right?                   high confidence           Database
 (PDF / photo)    claim data +            Fields missing?
                  confidence                    |
                                     fail / low confidence
                                                ↓
                                   [HUMAN REVIEW QUEUE]  ───────────→  [5. OUTPUT]
                                   Staff see scan + data side by side, fix, approve
```
- Colours: boxes 1–3 light blue, box 4 blue, review box orange, output box navy.
- Caption at the bottom: **"The AI only reads. Every number is checked by rules before it reaches the spreadsheet."**

## Slide 5: Key features & innovation showcase
- **Feature 1, Reads any format:** any hospital's bill or claim form, PDF or phone photo. No templates, no training.
- **Feature 2, Verifies the math:** checks line items against the subtotal, tax and grand total, plus missing fields. AI mistakes get caught.
- **Feature 3, Confidence + review:** every field gets a confidence score. Only uncertain bills go to a human.
- **Feature 4, Spreadsheet-ready:** clean structured data to Excel, CSV or a database in one click. Click any value to see where it was read on the scan.

**What makes your solution unique?**
Other tools trust the AI. Hayara.ai checks it: every number is verified by rules before it is exported.

**Your unique selling point:**
Verified bill data in seconds instead of minutes of retyping, with a human only where it matters.

## Slide 6: Impact, feasibility & future scope
**Impact**
- **Target users / beneficiaries:** hospital billing desks, insurance / TPA claim processors, and patients
- **Expected benefits:** seconds per bill instead of minutes; fewer typing errors and claim rejections
- **How will you measure success?** Field accuracy on labelled datasets (CORD, SROIE), time per bill, and the % of bills auto-approved

**Future scope**
- **Planned improvements:** overcharge alerts against government rates (CGHS / NPPA); a bill vs claim-form cross-check; regional-language bills
- **Scalability or next steps:** an API for hospital and insurer systems; batch processing; can run on a model hosted by the hospital, for privacy
- **Feasibility** (add as one line): built on proven pretrained models and open tools, with no training risk. MVP tonight, full app tomorrow.

## Rules
- No made-up statistics or accuracy numbers today. Real numbers come tomorrow.
- Keep the template's fonts and colours. Body text no smaller than about 18pt (the slides are large).
