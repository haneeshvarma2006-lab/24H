"""Learned field finder for local mode: which OCR line holds the total, the date, the hospital...

Trained by scripts/train_fields.py on labelled receipts (SROIE) + every bill a human approved in Hayara.
The rules in ocr_extract.py run first; the model fills or overrides fields, whichever measured better.
"""
import re
from functools import lru_cache
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "model" / "fields.joblib"
MONEY = {"subtotal", "discount", "tax", "total", "claimed_amount"}
DATE_RE = re.compile(r"\d{1,2}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{2,4}")
NUM_RE = re.compile(r"\d[\d,]*\.\d{2}\b|\d[\d,]*")


def featurize(lines: list[str]) -> list[str]:
    """Line text plus layout tokens the character n-grams can pick up."""
    money = [i for i, t in enumerate(lines) if re.search(r"\d[\d,]*\.\d{2}\b", t)]
    out = []
    for i, t in enumerate(lines):
        tags = [f"POS{min(9, i * 10 // max(len(lines), 1))}", f"IDX{min(i, 5)}"]
        tags += ["HASDATE"] if DATE_RE.search(t) else []
        tags += ["HASMONEY"] if i in money else []
        tags += ["LASTMONEY"] if money and i in money[-3:] else []
        tags += ["UPPER"] if t.isupper() else []
        out.append(f"{t.lower()} {' '.join(tags)}")
    return out


def value_from(line: str, field: str) -> str:
    """Pull the value out of a line the model picked."""
    if field in MONEY:
        nums = re.findall(r"\d[\d,]*\.\d{2}\b", line) or NUM_RE.findall(line)
        return nums[-1].replace(",", "") if nums else ""  # amount sits at the end of the line
    if field.endswith("_date"):
        m = DATE_RE.search(line)
        return re.sub(r"\s", "", m.group()).replace("/", "-").replace(".", "-") if m else ""
    from backend.ocr_extract import LABEL_RE
    return " ".join(LABEL_RE.sub(" ", line).split()).strip(" :-")


@lru_cache(maxsize=1)
def load(path=MODEL_PATH):
    if not Path(path).exists():
        return None
    import joblib
    return joblib.load(path)


def predict(lines: list[str], model) -> dict:
    """{field: (line index, probability)} for the most likely line of each field."""
    if not lines:
        return {}
    probs = model["pipeline"].predict_proba(featurize(lines))
    best = {}
    for k, field in enumerate(model["pipeline"].classes_):
        if field != "other":
            i = int(probs[:, k].argmax())
            best[field] = (i, float(probs[i, k]))
    return best


def apply(lines: list[str], values: dict, conf: dict, model=None) -> None:
    """Fill (or, if that measured better, override) rule-based values in place."""
    model = model or load()
    if model is None:
        return
    for field, (i, p) in predict(lines, model).items():
        mode = model["mode"].get(field, "rules")  # unmeasured fields stay with the rules
        if p < model["threshold"] or mode == "rules" or (field in values and mode != "override"):
            continue
        v = value_from(lines[i], field)
        if v:
            values[field], conf[field] = v, round(p, 2)
