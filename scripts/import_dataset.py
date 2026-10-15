"""Turn a downloaded public receipt dataset into data/samples + data/truth for eval.py.

python scripts/import_dataset.py cord  path/to/cord  --limit 100
python scripts/import_dataset.py sroie path/to/sroie --limit 100

Finds every image under the folder and pairs it with the label file of the same name (.json or .txt).
CORD labels: {"gt_parse": {"menu": [...], "sub_total": {...}, "total": {...}}} (or the same inside "ground_truth").
SROIE labels: {"company", "date", "address", "total"}.
Receipts only label some of our fields, so each truth file lists the fields that were labelled
and eval.py scores only those.
"""
import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.extract import FIELDS  # noqa: E402

IMAGES = {".jpg", ".jpeg", ".png", ".webp"}


def rupiah(text):
    """CORD prices are whole Indonesian rupiah written '60.000' or '60,000': keep sign and digits only."""
    text = str(text or "").strip()
    digits = re.sub(r"\D", "", text)
    return ("-" if text.startswith("-") and digits else "") + digits


def first(value):
    """CORD stores a field as a string, or as a list of strings when it spans several lines."""
    return " ".join(value) if isinstance(value, list) else str(value or "")


def cord(label: dict):
    parse = label.get("gt_parse") or json.loads(label.get("ground_truth", "{}")).get("gt_parse", {})
    menu = parse.get("menu", [])
    menu = [menu] if isinstance(menu, dict) else menu
    sub, total = parse.get("sub_total") or {}, parse.get("total") or {}
    values = {"subtotal": rupiah(first(sub.get("subtotal_price"))), "discount": rupiah(first(sub.get("discount_price"))),
              "tax": rupiah(first(sub.get("tax_price"))), "total": rupiah(first(total.get("total_price")))}
    items = [{"description": first(m.get("nm")), "qty": re.sub(r"[^\d.]", "", first(m.get("cnt"))),
              "rate": rupiah(first(m.get("unitprice"))), "amount": rupiah(first(m.get("price")))} for m in menu]
    return values, items, [k for k, v in values.items() if v]


def sroie(label: dict):
    values = {"hospital_name": label.get("company", ""), "hospital_address": label.get("address", ""),
              "bill_date": label.get("date", ""), "total": label.get("total", "")}
    return values, [], [k for k, v in values.items() if v]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["cord", "sroie"])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    labels = defaultdict(list)  # SROIE keeps OCR boxes and labels as two .txt files with the same name
    for p in args.folder.rglob("*"):
        if p.suffix.lower() in (".json", ".txt"):
            labels[p.stem].append(p)
    samples, truths = ROOT / "data" / "samples", ROOT / "data" / "truth"
    samples.mkdir(parents=True, exist_ok=True)
    truths.mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    for image in sorted(p for p in args.folder.rglob("*") if p.suffix.lower() in IMAGES):
        if done >= args.limit:
            break
        parsed = None
        for label in labels.get(image.stem, []):
            try:
                parsed = (cord if args.kind == "cord" else sroie)(json.loads(label.read_text(errors="replace")))
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue
            if parsed[2]:
                break
        if not parsed or not parsed[2]:
            skipped += 1
            continue
        values, items, labelled = parsed
        name = f"{args.kind}_{image.stem}"
        shutil.copy(image, samples / (name + image.suffix.lower()))
        (truths / f"{name}.json").write_text(json.dumps({
            "document_type": "bill",
            "fields": {f: {"value": values.get(f, ""), "confidence": 1.0} for f in FIELDS},
            "line_items": [i | {"confidence": 1.0} for i in items],
            "labelled": labelled,          # score only these fields
            "items_labelled": args.kind == "cord",
            "check_verdict": False,        # receipts carry no planted mistakes
        }, indent=2, ensure_ascii=False))
        done += 1
    print(f"imported {done} {args.kind} receipts into data/samples and data/truth ({skipped} skipped: no or bad label)")


if __name__ == "__main__":
    main()
