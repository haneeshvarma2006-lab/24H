# PPT content: Sprint 1 submission (due 4:30 PM)

10 slides. Copy the text exactly. **[brackets]** = something you fill in or a visual to add.
Design: white background, one accent colour (teal or blue), one font (Poppins or Inter), maximum 5 bullets per slide, large text.

---

## Slide 1: Title
- **ClaimLens**
- *AI reads the bill. Math checks the AI. A human approves only what's uncertain.*
- INNOHACKS 2.0 · AI Automation · Problem Statement #3: Hospital Bill and Insurance Reader
- Team **[Team name]** · [Member 1], [Member 2], [Member 3], [Member 4] · [College]

**Visual:** a crumpled hospital bill on the left, an arrow, a clean spreadsheet on the right.

---

## Slide 2: The Problem
- Every hospital uses a **different bill format**: different layouts, item names and handwritten parts
- Billing and insurance staff **retype every bill by hand** into spreadsheets and claim systems
- Retyping is **slow and causes typos**: wrong amounts, missed items, rejected claims
- **Overcharging goes unnoticed**: nobody compares each item against standard rates
- Simple OCR tools give **raw text, not usable data**, and can't tell when they're wrong

**Visual:** 3 different-looking hospital bills side by side, captioned "Same information, three formats".

---

## Slide 3: Who suffers
| Who | Pain |
|---|---|
| Hospital billing desk | Hours of manual data entry every day |
| Insurance (TPA) staff | Checking claims against bills line by line |
| Patients | Delayed or rejected claims, overcharges they never notice |

---

## Slide 4: Our Solution: ClaimLens
Upload any bill or claim form (PDF or phone photo), get **clean, verified, structured data**.

1. **Extract:** an AI vision model reads patient details, line items, charges and claim data
2. **Validate:** our checks verify the math: items add up to the total, tax is correct, no required field is missing
3. **Flag overcharges:** compare charges with government reference rates (CGHS package rates, NPPA drug ceiling prices)
4. **Human-in-the-loop:** only uncertain or failed bills go to a reviewer
5. **Export:** one click to Excel, CSV or a database

---

## Slide 5: How it works (architecture)
**Visual:** draw these as boxes with arrows:

```
[Bill / Claim form upload]
        ↓
[AI Vision Extraction] → structured data + confidence per field
        ↓
[Validation Engine]  ← CGHS / NPPA reference rates
   ├── All checks pass → ✅ Auto-approved
   └── Fails / low confidence → ⚠️ Review queue → human fixes it
        ↓
[Dashboard] → [Excel / CSV / Database]
```

Caption: **"The AI only reads. Every number is checked by our rules before it's trusted."**

---

## Slide 6: What makes us different (USP)
| Typical solution | ClaimLens |
|---|---|
| Sends the bill to an AI model and trusts the answer | **Checks the math on every bill** and catches the AI's mistakes |
| Gives text | Gives **structured data** ready for a spreadsheet or database |
| One format only | **Any hospital's format**, no templates to set up |
| No idea when it's wrong | **Confidence score per field** + review queue |
| Just reads | **Detects overcharging** against government rates |
| Black box | **Click any value** to see where it came from on the scan |

---

## Slide 7: Tech stack
- **Backend:** Python, FastAPI
- **AI:** pretrained vision model ([Claude / Gemini], whichever key you use). **No training needed**, so it works on any format from day one
- **Database:** SQLite (PostgreSQL in production)
- **Frontend:** HTML / JavaScript dashboard
- **Export:** Excel / CSV
- **Evaluation data:** public labelled receipt and form datasets (CORD, SROIE, FUNSD) to **measure** accuracy
- **Reference data:** CGHS rate list, NPPA ceiling price list

---

## Slide 8: Feasibility & plan
| Phase | Deliverable |
|---|---|
| Sprint 1 (today) | Idea, architecture, datasets collected |
| Sprint 2 (tonight) | MVP: upload → extract → validate → export |
| Sprint 3 (tomorrow) | Review dashboard, overcharge detection, accuracy report |

**Risk handling:**
- AI misreads a field → low confidence or failed math check → human review. **Nothing wrong is exported silently**
- Internet down → cached results for the demo bills
- Patient privacy → demo uses only made-up data; in production it can run on a model hosted by the hospital

---

## Slide 9: Impact
- **Minutes → seconds** per bill (no manual retyping)
- **Fewer claim rejections** caused by typing errors
- **Overcharges caught automatically**, which protects patients
- Staff review **only the uncertain bills**, not every bill
- **Future:** regional-language bills, direct link to insurer/TPA systems, a patient app to check a bill before paying

---

## Slide 10: Thank you
- **ClaimLens:** *verified bill data, not just extracted text.*
- Team [name] · [members]
- [GitHub link: github.com/haneeshvarma2006-lab/24H]

---

## Rules for the deck
- **Do not invent statistics.** If you add a number (e.g. "X lakh claims per year"), it needs a source written on the slide. Judges check.
- No paragraphs. If a bullet wraps to 3 lines, cut it.
- Slides 4, 5 and 6 matter most. Spend your time there.
- Results slide (accuracy %, time per bill) comes **tomorrow** with real numbers. Do not put fake numbers in today's deck.

## Speaker notes (1 line per slide, if presenting)
1. "We're ClaimLens. We turn messy hospital bills into verified data."
2. "Every hospital bill looks different, so staff retype them by hand. It's slow and full of errors."
3. "It hurts billing staff, insurers and, most of all, patients."
4. "Upload any bill and we extract, validate, flag overcharges and export."
5. "The AI only reads. Our validation engine decides what's trusted."
6. "Other tools trust the AI. We check it."
7. "No training needed. We use a pretrained model and measure it on public datasets."
8. "MVP tonight, full app tomorrow, and every risk has a fallback."
9. "Seconds instead of minutes, fewer rejected claims, patients protected."
10. "Thank you. Happy to show a live demo."
