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
100 receipts imported from `D:\datasets\datasets\SROIE\archive\SROIE2019` (0 skipped). Eval not run yet (quota).
