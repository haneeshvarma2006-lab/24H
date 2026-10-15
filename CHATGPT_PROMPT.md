# Prompt to paste into ChatGPT

Copy everything inside the box below.

```
You are my hackathon teammate and coach. Guide me step by step, one task at a time, and wait for me to say "done" before moving to the next task. Keep answers short and practical.

CONTEXT
- Hackathon: INNOHACKS 2.0 (TECHSPARK 2026). Today is 15 Oct. Sprint 1 (problem statement + PPT) must be submitted by 4:30 PM (last window 5:00 PM). MVP is due 11:30 PM tonight. Final app and judging are tomorrow.
- Problem statement: AI Automation #3, "Hospital Bill and Insurance Reader". Hospital bills and insurance papers are long, messy and different at every hospital. Staff retype them by hand, which is slow and error-prone. Build a tool that reads scanned bills and forms and extracts patient details, charges and claim data. Output must be clean, organized data ready for a spreadsheet or database.
- Our project: MediParse. Pitch: "AI reads the bill. Math checks the AI. A human approves only what's uncertain."
- Pipeline: Upload (PDF/photo) -> AI extraction with a pretrained vision model (Google Gemini API, NO training) -> Validation rules (line items = subtotal, subtotal - discount + tax = total, qty x rate = amount, required fields, duplicate items, confidence < 0.8) -> pass = auto-approved, fail = human review queue -> export to Excel/CSV/JSON/database.
- Stack: Python, FastAPI, SQLite, Gemini API, Tesseract OCR (for click-to-source), HTML/JS dashboard.
- Another teammate (Claude) is building the backend. My job is listed below.

MY TASKS (in this order)

TASK 1: Finish the PPT in the official 6-slide InnoHack template (deadline 4:30 PM). Do NOT add slides. Keep the template's fonts and colours. Help me fit this text into each slide, cut words if a box overflows, and check for typos.

Slide 1 (Title): Project title "MEDIPARSE". Subtitle "AI Hospital Bill & Insurance Reader". Team name, member names, college: I will fill. Problem statement ID: "AI Automation – 3 (Hospital Bill and Insurance Reader)".

Slide 2 (Problem statement + Proposed solution):
Problem: Hospital bills and insurance papers are long, messy and different at every hospital. Staff retype them by hand, which is slow and error-prone.
- Every hospital uses its own layout, so no fixed template works
- Manual retyping causes wrong amounts, missed line items and rejected or delayed claims
- Plain OCR gives raw text, not clean data, and never says when it is wrong
Proposed solution: MediParse reads scanned bills and claim forms and returns clean, verified data ready for a spreadsheet or database.
- Extract: a pretrained AI vision model pulls patient details, line-item charges, totals and claim data from any format
- Verify: our rule engine checks the math (line items = subtotal, tax, grand total) and missing fields, with a confidence score per field
- Review & export: only uncertain bills go to a human; one click to Excel, CSV or database

Slide 3 (Technology stack, 6 boxes):
01 Programming languages: Python, JavaScript, SQL
02 Frontend: HTML5, CSS, JavaScript; review dashboard with the scan and data side by side
03 Backend: FastAPI (Python), Pydantic for data validation, openpyxl for Excel export
04 Database & storage: SQLite (MVP), PostgreSQL (production), local storage for scans
05 AI/ML & APIs (fix the template typo "A/ML"): Google Gemini vision API (pretrained, no training), Tesseract OCR; CORD, SROIE, FUNSD public datasets to measure accuracy
06 Cloud & dev tools: Git & GitHub, VS Code, Postman; deploy on Render / Railway

Slide 4 (Architecture & workflow): I have a ready diagram image (workflow.png). Help me place and size it, and add the caption: "The AI only reads. Every number is checked by rules before it reaches the spreadsheet."

Slide 5 (Key features & innovation):
Feature 1 – Reads any format: any hospital's bill or claim form, PDF or phone photo. No templates, no training.
Feature 2 – Verifies the math: line items vs subtotal, tax and grand total, plus missing fields. AI mistakes get caught.
Feature 3 – Confidence + review: every field gets a confidence score. Only uncertain bills go to a human.
Feature 4 – Spreadsheet-ready: clean structured data to Excel, CSV or database in one click.
What makes it unique: Other tools trust the AI. MediParse checks it: every number is verified by rules before it is exported.
USP: Verified bill data in seconds instead of minutes of retyping, with a human only where it matters.

Slide 6 (Impact, feasibility & future scope):
Target users: hospital billing desks, insurance/TPA claim processors, patients
Expected benefits: seconds per bill instead of minutes; fewer typing errors and claim rejections
How we measure success: field accuracy on labelled datasets, time per bill, % of bills auto-approved
Planned improvements: overcharge alerts vs government rates (CGHS / NPPA); bill vs claim-form cross-check; regional-language bills
Scalability: API for hospital and insurer systems; batch processing. Every reviewer correction is saved as labelled data, so we can fine-tune our own model later.
Feasibility: proven pretrained models + open tools, no training risk. MVP tonight, full app tomorrow.

RULES FOR THE PPT
- No invented statistics or accuracy numbers. Real numbers come tomorrow.
- Body text not smaller than about 18pt (the slides are large). Max 5 bullets per box.
- Before I submit, give me a final checklist (names filled, no placeholder text left, typo check, export as PDF too).

TASK 2 (after PPT is submitted): Get a free Gemini API key from aistudio.google.com and set it as the environment variable GEMINI_API_KEY on my laptop (Windows: setx GEMINI_API_KEY "..." then open a new terminal). Never paste the key into chat or code.

TASK 3: Install Tesseract OCR on my laptop (Windows installer) and add it to PATH. Verify with: tesseract --version

TASK 4: Collect demo data (no real patient data, ever):
- 15-20 Indian hospital / pharmacy bill images with different layouts (search "hospital bill format India", "pharmacy bill India")
- 1 blank IRDAI health claim form (Part A + Part B), filled 5 times with made-up data
- 10 phone photos of printed bills (angled, crumpled)
- In 2-3 bills, plant deliberate mistakes: wrong total, missing patient name, duplicated line item
- For 5 bills, type the correct values into a sheet (patient name, date, every line item, subtotal, tax, total)
- Name files bill_01.jpg, bill_02.jpg, claim_01.pdf ... and put them in one folder

Start with TASK 1 now. Ask me which slide I'm on.
```
