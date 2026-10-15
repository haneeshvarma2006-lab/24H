"""Train the local field finder (backend/field_model.py). CPU only, minutes.

python scripts/train_fields.py                 # all data/truth docs with a scan + approved bills in hayara.db
python scripts/train_fields.py --only sroie     # one dataset

1. OCR every training scan once (cached in data/ocr_cache, so reruns are fast).
2. Label each OCR line with the field whose correct value it contains.
3. Train TF-IDF char n-grams + logistic regression; hold out 20% of documents.
4. On the held-out documents compare: rules only / model fills gaps / model overrides, per field,
   and save the best choice per field with the model in data/model/fields.joblib.
"""
import argparse
import hashlib
import json
import mimetypes
import random
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.field_model import MODEL_PATH, MONEY, featurize, predict, value_from  # noqa: E402
from backend.ocr_extract import ocr_lines, parse, pdf_text_lines, to_png  # noqa: E402
from backend.validate import amount  # noqa: E402
from eval import same  # noqa: E402

FIELDS = ["hospital_name", "hospital_address", "patient_name", "bill_no", "bill_date", "subtotal", "tax", "total"]
CACHE = ROOT / "data" / "ocr_cache"


def lines_for(data: bytes, mime: str) -> list[tuple[str, float]]:
    key = CACHE / f"{hashlib.sha256(data).hexdigest()}.json"
    if key.exists():
        return [tuple(x) for x in json.loads(key.read_text())]
    lines = pdf_text_lines(data) if mime == "application/pdf" else []
    if len(lines) < 5:
        lines = ocr_lines(to_png(data, mime))
    CACHE.mkdir(parents=True, exist_ok=True)
    key.write_text(json.dumps(lines))
    return lines


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def label(lines: list[str], truth: dict) -> list[str]:
    """Each OCR line gets the field whose correct value it contains (else 'other')."""
    labels = ["other"] * len(lines)
    for field in FIELDS:
        want = str(truth.get(field, "")).strip()
        if not want:
            continue
        hits = []
        for i, t in enumerate(lines):
            if field in MONEY:
                ok = any(abs((amount(n) or -1) - amount(want)) < 0.01 for n in re.findall(r"\d[\d,]*\.?\d*", t)) \
                    if amount(want) is not None else False
            elif field.endswith("_date"):
                ok = re.sub(r"\D", "", want) in re.sub(r"\D", "", t) and len(re.sub(r"\D", "", want)) >= 6
            elif field == "hospital_address":  # addresses span several lines
                ok = len(norm(t)) >= 6 and norm(t) in norm(want)
            else:
                ok = len(norm(want)) >= 3 and (norm(want) in norm(t) or (len(norm(t)) >= 6 and norm(t) in norm(want)))
            if ok:
                hits.append(i)
        if field in MONEY and hits:
            hits = hits[-1:]  # the same number also appears as a line item or subtotal; totals sit lowest
        for i in hits:
            if labels[i] == "other":
                labels[i] = field
    return labels


def documents(only: str | None):
    """(name, ocr lines, {field: correct value}) from data/truth + approved bills in hayara.db."""
    for truth_file in sorted((ROOT / "data" / "truth").glob(f"{only or ''}*.json")):
        scan = next(iter((ROOT / "data" / "samples").glob(truth_file.stem + ".*")), None)
        if scan:
            t = json.loads(truth_file.read_text())
            fields = {k: v["value"] for k, v in t["fields"].items()}
            scope = t.get("labelled") or [k for k in FIELDS if fields.get(k)]
            yield truth_file.stem, lines_for(scan.read_bytes(), mimetypes.guess_type(scan.name)[0]), \
                {k: fields.get(k, "") for k in FIELDS if k in scope}
    db = ROOT / "hayara.db"
    if only or not db.exists():
        return
    # every bill a human approved is verified data: the app keeps learning from its reviewers
    for r in sqlite3.connect(db).execute("SELECT id, stored_as, mime_type, data FROM bills WHERE status = 'approved'"):
        scan = ROOT / "data" / "uploads" / r[1]
        if scan.exists():
            fields = {k: v["value"] for k, v in json.loads(r[3])["fields"].items()}
            yield f"approved_{r[0]}", lines_for(scan.read_bytes(), r[2]), {k: fields.get(k, "") for k in FIELDS if fields.get(k)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="name prefix, e.g. sroie, bill")
    args = parser.parse_args()
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    import joblib

    docs = []
    for n, (name, lines, truth) in enumerate(documents(args.only), 1):
        docs.append((name, lines, truth))
        if n % 25 == 0:
            print(f"OCR'd {n} documents...")
    if len(docs) < 5:
        sys.exit(f"Only {len(docs)} labelled documents found; import a dataset first (scripts/import_dataset.py).")
    random.Random(42).shuffle(docs)
    cut = max(1, len(docs) // 5)
    test, train = docs[:cut], docs[cut:]

    X, y = [], []
    for _, lines, truth in train:
        texts = [t for t, _ in lines]
        X += featurize(texts)
        y += label(texts, truth)
    print(f"Training on {len(train)} documents ({len(X)} lines), testing on {len(test)} held-out documents")
    pipeline = make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2, sublinear_tf=True),
                             LogisticRegression(max_iter=2000, class_weight="balanced", C=4.0))
    pipeline.fit(X, y)
    model = {"pipeline": pipeline, "threshold": 0.5, "mode": {}}

    # held-out comparison per field: rules / rules + model fills gaps / model overrides
    score = {f: {"rules": 0, "fill": 0, "override": 0, "n": 0} for f in FIELDS}
    for _, lines, truth in test:
        texts = [t for t, _ in lines]
        rules = {k: v["value"] for k, v in parse(lines, learned=False)["fields"].items()}
        picks = predict(texts, model)
        for f, want in truth.items():
            if f not in score or not want:
                continue
            guess = value_from(texts[picks[f][0]], f) if f in picks and picks[f][1] >= model["threshold"] else ""
            score[f]["n"] += 1
            score[f]["rules"] += same(f, rules.get(f, ""), want)
            score[f]["fill"] += same(f, rules.get(f) or guess, want)
            score[f]["override"] += same(f, guess or rules.get(f, ""), want)

    print(f"\n{'field':18} {'docs':>5} {'rules':>7} {'+fill':>7} {'+override':>10}  -> using")
    for f, s in score.items():
        if not s["n"]:
            continue
        mode = max(("rules", "fill", "override"), key=lambda m: (s[m], m == "rules"))  # ties keep the rules
        model["mode"][f] = mode
        pct = lambda m: f"{s[m] / s['n']:.0%}"
        print(f"{f:18} {s['n']:>5} {pct('rules'):>7} {pct('fill'):>7} {pct('override'):>10}  -> {mode}")
    total = lambda m: sum(s[m] for s in score.values())
    best = sum(s[model["mode"].get(f, "rules")] for f, s in score.items())
    n = total("n")
    print(f"\nHeld-out field accuracy: rules only {total('rules') / n:.1%}  ->  with trained model {best / n:.1%}  ({n} fields)")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Saved {MODEL_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
