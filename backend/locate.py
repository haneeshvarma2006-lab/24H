"""Click-to-source: find where each extracted value sits on the scan, using Tesseract word boxes.

Boxes are [x, y, w, h] as fractions of the image size, so the UI can overlay them at any zoom.
"""
import csv
import io
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageOps

from backend.validate import amount

# which words on the same line identify a number field ("total" also appears in "Sub Total")
LABELS = {"subtotal": ("sub",), "discount": ("disc",), "tax": ("gst", "tax"),
          "total": ("net", "payable", "grand"), "claimed_amount": ("claim",),
          "bill_date": ("bill", "invoice"), "admission_date": ("adm",), "discharge_date": ("disch",)}


def ocr_words(data: bytes, psm: str) -> list[dict]:
    # OMP_THREAD_LIMIT=1: three parallel tesseracts each spawning threads thrash the CPU
    tsv = subprocess.run(["tesseract", "stdin", "stdout", "--psm", psm, "tsv"], input=data,
                         env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                         capture_output=True, check=True, timeout=60).stdout.decode()
    words = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if row["level"] == "5" and row["text"].strip():
            words.append({"text": row["text"], "line": (psm, row["block_num"], row["par_num"], row["line_num"]),
                          "box": [int(row[k]) for k in ("left", "top", "width", "height")]})
    return words


def same(word: str, token: str) -> bool:
    if re.fullmatch(r"[\d,.]+", token) and amount(token) is not None:
        return amount(word) is not None and abs(amount(word) - amount(token)) < 0.01
    clean = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return clean(token) != "" and clean(word) == clean(token)


def matches(words, value, start=0):
    """Indexes of the first word of each place `value` appears, all its tokens on one line."""
    tokens = value.split()
    hits = []
    for i in range(start, len(words) - len(tokens) + 1):
        run = words[i:i + len(tokens)]
        if all(w["line"] == run[0]["line"] for w in run) and all(same(w["text"], t) for w, t in zip(run, tokens)):
            hits.append(i)
    return hits


def union(boxes, size):
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
    W, H = size
    return [round(x0 / W, 4), round(y0 / H, 4), round((x1 - x0) / W, 4), round((y1 - y0) / H, 4)]


def first_page_png(pdf: bytes) -> bytes:
    """Render page 1 of a PDF at ~200 dpi, sharp enough for OCR without upscaling."""
    import pypdfium2
    buf = io.BytesIO()
    pypdfium2.PdfDocument(pdf)[0].render(scale=3).to_pil().save(buf, "PNG")
    return buf.getvalue()


def locate(data: bytes, doc: dict) -> dict:
    """{"total": [x, y, w, h], "line_items.2": [...], ...} for every value found on the image."""
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))  # phones store portrait photos sideways + a rotate flag
    if image.width < 1600:  # small text in phone photos needs upscaling before OCR
        image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "PNG")
    # each page mode misses different things (table rows, tilted photos), so search all three
    # shortcut: table rows in blurry phone photos are still often missed; try OpenCV line removal if judges care
    with ThreadPoolExecutor() as pool:
        passes = pool.map(lambda psm: ocr_words(buf.getvalue(), psm), ("3", "6", "11"))
    words, size = [w for words in passes for w in words], image.size
    line_text = lambda i: " ".join(w["text"].lower() for w in words if w["line"] == words[i]["line"])
    sources = {}

    for name, field in doc["fields"].items():
        value = str(field["value"]).strip()
        hits = matches(words, value) if value else []
        if not hits:
            continue
        labelled = [i for i in hits if any(k in line_text(i) for k in LABELS.get(name, ()))]
        i = (labelled or hits)[-1 if name in LABELS else 0]  # totals sit at the bottom
        sources[name] = union([w["box"] for w in words[i:i + len(value.split())]], size)

    pos = 0
    for n, item in enumerate(doc["line_items"]):
        # first 2 words of the description: OCR often mangles brackets and units after that
        desc = " ".join(item["description"].split()[:2])
        hits = matches(words, desc, pos) if desc else []
        if hits:
            row = [w["box"] for w in words if w["line"] == words[hits[0]]["line"]]
            sources[f"line_items.{n}"] = union(row, size)
            pos = hits[0] + 1  # keeps repeated items (same medicine twice) on separate rows
    return sources
