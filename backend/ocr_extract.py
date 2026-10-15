"""Fully local extraction: Tesseract OCR + label rules. No API, no quota, works offline.

Weaker than the vision model on unusual layouts, so confidences are lower and more bills go to review.
Returns the same shape as extract.extract().
"""
import csv
import io
import os
import re
import subprocess

from PIL import Image, ImageOps

from backend.extract import FIELDS

# label (regex, matched case-insensitively at a word boundary) -> field; order matters: longer labels first
LABELS = [
    (r"name of the patient|patient name|patient", "patient_name"),
    (r"uhid|mrn|reg\.? ?no", "uhid"),
    (r"age\s*/\s*(?:gender|sex)", "age_gender"),
    (r"age", "age"),
    (r"gender|sex", "gender"),
    (r"consultant|prescribed by|doctor|treating doctor", "doctor"),
    (r"bill no|invoice no|bill number|receipt no", "bill_no"),
    (r"date of admission|admission date|admission|admitted", "admission_date"),
    (r"date of discharge|discharge date|discharge|discharged", "discharge_date"),
    (r"bill date|invoice date|date", "bill_date"),
    (r"insurance company|insurer", "insurer"),
    (r"tpa", "tpa"),
    (r"policy number|policy no", "policy_no"),
    (r"claim number|claim no", "claim_no"),
    (r"total amount claimed(?: \(rs\.?\))?|amount claimed", "claimed_amount"),
    (r"sub ?total", "subtotal"),
    (r"discount", "discount"),
    (r"gst|tax", "tax"),
    (r"net payable|grand total|net amount|total amount|amount payable|total", "total"),
    (r"name of hospital|hospital name", "hospital_name"),
]
LABEL_RE = re.compile(r"(?<![\w-])(" + "|".join(f"(?:{p})" for p, _ in LABELS) + r")(?![\w])\s*[:=\-]?", re.I)
MONEY = {"subtotal", "discount", "tax", "total", "claimed_amount"}
NUM = r"[\d,]+(?:\.\d+)?"
ITEM_RE = re.compile(rf"^\W*(?:\d{{1,3}}\s*[_|.\]]*\s+)?(.*?[A-Za-z].*?)\s+(?:(\d+(?:\.\d+)?)\s+)?({NUM})\s+({NUM})\s*$")


def ocr_lines(image_png: bytes, psm: str = "4") -> list[tuple[str, float]]:
    """(text, mean word confidence 0-1) per line, top to bottom. --psm 4 keeps table rows intact."""
    tsv = subprocess.run(["tesseract", "stdin", "stdout", "--psm", psm, "tsv"], input=image_png,
                         capture_output=True, check=True, timeout=60).stdout.decode()
    lines = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row["level"] == "5" and row["text"].strip():
            key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
            lines.setdefault(key, []).append((row["text"], max(float(row["conf"]), 0) / 100))
    out = []
    for _, ws in sorted(lines.items()):
        real = [c for w, c in ws if re.search(r"[A-Za-z0-9]", w)] or [0.0]  # junk like "=", "|" carries no value
        out.append((" ".join(w for w, _ in ws).replace("|", " "), sum(real) / len(real)))
    return out


def to_png(data: bytes, mime_type: str) -> bytes:
    if mime_type == "application/pdf":
        from backend.locate import first_page_png
        data = first_page_png(data)
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if image.width < 1600:  # small text needs upscaling before OCR
        image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def field_for(label: str) -> str:
    return next(f for p, f in LABELS if re.fullmatch(p, label.strip(), re.I))


def clean(value: str, field: str) -> str:
    value = value.strip(" :=-_|.,")
    if field in MONEY:
        m = re.search(NUM, value)
        return m.group().replace(",", "") if m else ""
    if field.endswith("_date"):
        m = re.search(r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}", value)
        return m.group().replace("/", "-").replace(".", "-") if m else ""
    return " ".join(value.split())


def parse(lines: list[tuple[str, float]]) -> dict:
    values, conf, items = {}, {}, []
    text = " ".join(t for t, _ in lines).lower()
    for text_line, c in lines:
        item = ITEM_RE.match(text_line)
        if item and not LABEL_RE.match(text_line.strip()):
            desc, qty, rate, amt = item.groups()
            r, a = float(rate.replace(",", "")), float(amt.replace(",", ""))
            if qty is None and r and (a / r).is_integer():  # OCR often drops the narrow qty column
                qty = str(int(a / r))
            items.append({"description": desc.strip(" _-"), "qty": qty or "", "rate": rate.replace(",", ""),
                          "amount": amt.replace(",", ""), "confidence": round(c, 2)})
            continue
        found = list(LABEL_RE.finditer(text_line))
        # a value runs to the next label of a different field ("MediAssist TPA" stays whole)
        found = [m for i, m in enumerate(found) if i == 0 or field_for(m.group(1)) != field_for(found[i - 1].group(1))]
        for i, m in enumerate(found):
            field = field_for(m.group(1))
            raw = text_line[m.end():found[i + 1].start() if i + 1 < len(found) else None]
            if field == "age_gender":  # "45 / Male" or "34 Female"
                age, _, gender = raw.partition("/") if "/" in raw else raw.strip().partition(" ")
                pairs = [("age", age), ("gender", gender)]
            else:
                pairs = [(field, raw)]
            for f, v in pairs:
                v = clean(v, f)
                if v and f not in values:  # first occurrence wins (e.g. "Total" inside "Sub Total" is matched as subtotal)
                    values[f], conf[f] = v, round(c, 2)

    # hospital name and address: the first text lines above any label
    head = [(t.strip(), c) for t, c in lines[:4] if re.search(r"[A-Za-z]{3}", t) and not LABEL_RE.search(t)]
    if head and "hospital_name" not in values:
        values["hospital_name"], conf["hospital_name"] = head[0][0], round(head[0][1], 2)
        if len(head) > 1 and re.search(r"\d", head[1][0]):
            values["hospital_address"] = re.split(r"\s*[-·•]\s*ph\b|\s+ph\s*[:.]", head[1][0], flags=re.I)[0].strip()
            conf["hospital_address"] = round(head[1][1], 2)
    claim = "claim form" in text
    if claim:  # the only date on a claim form besides admission/discharge is the signature date
        values.pop("bill_date", None)
    return {
        "document_type": "claim_form" if claim else "bill",
        "fields": {f: {"value": values.get(f, ""), "confidence": conf.get(f, 1.0)} for f in FIELDS},
        "line_items": items,
    }


def pdf_text_lines(pdf: bytes) -> list[tuple[str, float]]:
    """Digital PDFs carry their text: read it exactly instead of OCR-ing a picture of it."""
    import pypdfium2
    text = pypdfium2.PdfDocument(pdf)[0].get_textpage().get_text_range()
    return [(t.strip(), 0.99) for t in text.splitlines() if t.strip()]


def ocr_extract(data: bytes, mime_type: str) -> dict:
    if mime_type == "application/pdf":
        lines = pdf_text_lines(data)
        if len(lines) >= 5:  # scanned PDFs have no text layer and fall through to OCR
            return parse(lines)
    png = to_png(data, mime_type)
    doc = parse(ocr_lines(png))
    filled = sum(1 for f in doc["fields"].values() if f["value"])
    if filled < 6 or not doc["line_items"]:  # blurry or tilted photo: a second page mode fills the gaps
        extra = parse(ocr_lines(png, "6"))
        for name, f in extra["fields"].items():
            if not doc["fields"][name]["value"] and f["value"]:
                doc["fields"][name] = f
        if len(extra["line_items"]) > len(doc["line_items"]):
            doc["line_items"] = extra["line_items"]
    return doc
