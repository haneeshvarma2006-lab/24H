# Eval results

Run 2026-10-15 on the laptop, model `gemini-3.8-flash` (`gemini-2.5-flash` now returns 404 for new keys).
**Incomplete:** the free tier allows 20 requests/day per model, and failed 503 "high demand" calls seem to count toward that limit.
The quota ran out partway through the demo bills, so the CORD and SROIE evals have not run yet.

## Smoke test (dashboard upload)
`bill_02.png` → status `review`, issue `total_math`: "₹5,730.00 − discount ₹0.00 + tax ₹0.00 = ₹5,730.00, but total says ₹6,530.00" (as expected).

## `python eval.py --only bill --delay 5`
Two runs. Each covered different bills; the others failed with 503/429. No bill was scored twice.

Run 1 (bill_02, bill_03, bill_04 failed with 503):
```
bill_01.png              fields 17/17  items 5/5  verdict approved (expected approved)  14.1s
bill_05_photo.jpg        fields 16/17  items 5/5  verdict approved (expected approved)  33.7s  wrong: hospital_address
bill_06.png              fields 12/13  items 5/5  verdict review (expected review)  25.8s  wrong: uhid
bill_07.pdf              fields 16/17  items 4/4  verdict approved (expected approved)  22.9s  wrong: hospital_address

bill: 4 documents
  Field accuracy:        95.3%  (61/64)
  Line-item accuracy:    100.0%  (19/19)
  Correct verdict:       100.0%  (4/4)  (planted mistakes caught, clean bills approved)
  Average time per bill: 24.1s
```

Run 2 (bill_01, bill_02, bill_05, bill_06, bill_07 failed with 429, daily quota):
```
bill_03.png              fields 9/9  items 5/5  verdict review (expected review)  92.9s
bill_04.png              fields 12/12  items 4/4  verdict approved (expected approved)  56.4s

bill: 2 documents
  Field accuracy:        100.0%  (21/21)
  Line-item accuracy:    100.0%  (9/9)
  Correct verdict:       100.0%  (2/2)  (planted mistakes caught, clean bills approved)
  Average time per bill: 74.7s
```
`bill_02` was not scored by eval. The smoke test above shows its planted mistake is caught.

## CORD
Not run: there is no CORD folder in `D:\datasets`.

## SROIE
600 receipts imported from `D:\datasets\datasets\SROIE\archive\SROIE2019` (0 skipped). Gemini eval not run (quota); used to train the local model below.

## Trained local model
Run 2026-10-15 on the laptop, no Gemini calls. 600 SROIE receipts imported (`--limit 600`, 0 skipped), OCR'd with Tesseract,
`python scripts/train_fields.py`: 80/20 split by document (seed 42), no approved bills in `hayara.db` yet.
```
Training on 488 documents (14462 lines), testing on 121 held-out documents

field               docs   rules   +fill  +override  -> using
hospital_name        121     34%     34%        40%  -> override
hospital_address     120      0%      0%         2%  -> rules
patient_name           1    100%    100%       100%  -> rules
bill_date            120     29%     50%        52%  -> fill
total                120     20%     25%        40%  -> fill

Held-out field accuracy: rules only 21.0%  ->  with trained model 28.8%  (482 fields)
```
Override measured best for bill_date (52%), total (40%) and hospital_address (2%), and with it the held-out score was 33.4%.
But on the demo documents it changed bill_05_photo's date (08-10-2026 instead of 10-10-2026) and sent the clean bill_07.pdf
to review (`low_confidence:total`). So `train_fields.py` caps those three fields at "fill" (`NO_OVERRIDE`).
With the model as saved, the 9 demo documents in local mode give the same results as with rules only: bill_01, bill_04, bill_07, claim_01
approved; bill_02 total_math, bill_03 required patient_name + duplicate, bill_06 line_math, claim_02 claim_match, bill_05_photo review (items_sum).
These numbers are on SROIE (Malaysian shop receipts, labelled company/date/address/total only), not on hospital bills.
