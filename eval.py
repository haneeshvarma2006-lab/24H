"""Measure extraction accuracy against hand-checked answers. Real numbers for the slides.

python eval.py                     # every data/samples file that has data/truth/<name>.json
python eval.py --delay 5           # pause between bills (Gemini free tier rate limits)

Calls the model fresh (ignores the cache), so it costs one API call per bill.
"""
import argparse
import difflib
import json
import mimetypes
import re
import time
from pathlib import Path

from backend.extract import extract
from backend.validate import amount, validate

ROOT = Path(__file__).resolve().parent
NUMERIC = {"subtotal", "discount", "tax", "total", "claimed_amount", "age", "qty", "rate", "amount"}
DATES = {"bill_date", "admission_date", "discharge_date"}


def same(key: str, got: str, want: str) -> bool:
    got, want = str(got or "").strip(), str(want or "").strip()
    if not got or not want:
        return not got and not want
    if key in NUMERIC:
        return amount(got) is not None and amount(want) is not None and abs(amount(got) - amount(want)) < 0.01
    if key in DATES:  # 10/10/2026 == 10-10-2026
        return re.sub(r"\D", "", got) == re.sub(r"\D", "", want)
    norm = lambda s: " ".join(re.sub(r"[^\w\s]", " ", s.casefold()).split())
    return norm(got) == norm(want)


def compare(pred: dict, truth: dict) -> dict:
    """Counts for one bill. Fields empty in both are skipped so blanks don't inflate the score."""
    fields = [k for k in truth["fields"] if truth["fields"][k]["value"] or pred["fields"][k]["value"]]
    wrong = [k for k in fields if not same(k, pred["fields"][k]["value"], truth["fields"][k]["value"])]

    items_ok = 0
    for p, t in zip(pred["line_items"], truth["line_items"]):
        desc = difflib.SequenceMatcher(None, p["description"].casefold(), t["description"].casefold()).ratio()
        items_ok += desc >= 0.8 and all(same(c, p[c], t[c]) for c in ("qty", "rate", "amount"))

    expected = "review" if truth.get("mistake") else "approved"
    got = "review" if any(i["rule"] != "low_confidence" for i in validate(pred)) else "approved"
    return {"fields": len(fields), "fields_ok": len(fields) - len(wrong), "wrong": wrong,
            "items": len(truth["line_items"]), "items_found": len(pred["line_items"]), "items_ok": items_ok,
            "verdict_ok": got == expected, "expected": expected, "got": got}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0, help="seconds to wait between bills")
    args = parser.parse_args()

    rows = []
    for truth_file in sorted((ROOT / "data" / "truth").glob("*.json")):
        scan = next((p for p in (ROOT / "data" / "samples").glob(truth_file.stem + ".*")), None)
        if scan is None:
            continue
        start = time.time()
        try:
            pred = extract(scan.read_bytes(), mimetypes.guess_type(scan.name)[0], use_cache=False)
        except Exception as e:  # keep going: one bad call should not lose the whole run
            print(f"{scan.name:24} FAILED: {e}")
            continue
        r = compare(pred, json.loads(truth_file.read_text())) | {"name": scan.name, "seconds": time.time() - start}
        rows.append(r)
        print(f"{scan.name:24} fields {r['fields_ok']}/{r['fields']}  items {r['items_ok']}/{r['items']}"
              f"  verdict {r['got']} (expected {r['expected']})  {r['seconds']:.1f}s"
              + (f"  wrong: {', '.join(r['wrong'])}" if r["wrong"] else ""))
        time.sleep(args.delay)

    if not rows:
        return print("No bills evaluated.")
    total = lambda k: sum(r[k] for r in rows)
    print(f"\nBills: {len(rows)}")
    print(f"Field accuracy:       {total('fields_ok') / total('fields'):.1%}  ({total('fields_ok')}/{total('fields')})")
    print(f"Line-item accuracy:   {total('items_ok') / total('items'):.1%}  ({total('items_ok')}/{total('items')})")
    print(f"Correct verdict:      {total('verdict_ok')}/{len(rows)} bills (mistakes caught, clean bills approved)")
    print(f"Average time per bill: {total('seconds') / len(rows):.1f}s")


if __name__ == "__main__":
    main()
