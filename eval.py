"""Measure extraction accuracy against hand-checked answers. Real numbers for the slides.

python eval.py                     # every data/samples file that has data/truth/<name>.json
python eval.py --delay 5           # pause between bills (Gemini free tier rate limits)
python eval.py --only cord --limit 50

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
    """Counts for one bill. Fields empty in both are skipped so blanks don't inflate the score.
    Imported receipts list their "labelled" fields; anything else they show is unscored."""
    fields = truth.get("labelled") or [k for k in truth["fields"] if truth["fields"][k]["value"] or pred["fields"][k]["value"]]
    wrong = [k for k in fields if not same(k, pred["fields"][k]["value"], truth["fields"][k]["value"])]

    items_ok, items = 0, len(truth["line_items"]) if truth.get("items_labelled", True) else 0
    for p, t in zip(pred["line_items"], truth["line_items"][:items]):
        desc = difflib.SequenceMatcher(None, p["description"].casefold(), t["description"].casefold()).ratio()
        items_ok += desc >= 0.8 and all(same(c, p[c], t[c]) for c in ("qty", "rate", "amount"))

    expected = "review" if truth.get("mistake") else "approved"
    got = "review" if any(i["rule"] != "low_confidence" for i in validate(pred)) else "approved"
    checked = truth.get("check_verdict", True)
    return {"fields": len(fields), "fields_ok": len(fields) - len(wrong), "wrong": wrong,
            "items": items, "items_found": len(pred["line_items"]), "items_ok": items_ok,
            "verdicts": int(checked), "verdict_ok": int(checked and got == expected), "expected": expected, "got": got}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=0, help="seconds to wait between bills")
    parser.add_argument("--only", help="name prefix, e.g. bill, cord, sroie")
    parser.add_argument("--limit", type=int, default=10_000)
    args = parser.parse_args()

    rows = []
    truth_files = sorted((ROOT / "data" / "truth").glob(f"{args.only or ''}*.json"))[:args.limit]
    for truth_file in truth_files:
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
              + (f"  verdict {r['got']} (expected {r['expected']})" if r["verdicts"] else "") + f"  {r['seconds']:.1f}s"
              + (f"  wrong: {', '.join(r['wrong'])}" if r["wrong"] else ""))
        time.sleep(args.delay)

    if not rows:
        return print("No bills evaluated.")
    for group in sorted({r["name"].split("_")[0] for r in rows}) + ["ALL"]:
        rs = [r for r in rows if group == "ALL" or r["name"].split("_")[0] == group]
        total = lambda k: sum(r[k] for r in rs)
        pct = lambda a, b: f"{total(a) / total(b):.1%}  ({total(a)}/{total(b)})" if total(b) else "n/a"
        print(f"\n{group}: {len(rs)} documents")
        print(f"  Field accuracy:        {pct('fields_ok', 'fields')}")
        print(f"  Line-item accuracy:    {pct('items_ok', 'items')}")
        print(f"  Correct verdict:       {pct('verdict_ok', 'verdicts')}  (planted mistakes caught, clean bills approved)")
        print(f"  Average time per bill: {total('seconds') / len(rs):.1f}s")


if __name__ == "__main__":
    main()
