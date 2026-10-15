"""Scan of a bill or claim form -> structured fields, using a pretrained vision model.

This is the only file that knows which AI model is used.
"""
import hashlib
import json
import os
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, create_model

# shortcut: model name is a guess at what the free tier offers today, override with GEMINI_MODEL if it 404s
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"

FIELDS = [
    "patient_name", "uhid", "age", "gender",
    "hospital_name", "hospital_address", "doctor",
    "bill_no", "bill_date", "admission_date", "discharge_date",
    "subtotal", "discount", "tax", "total",
    "insurer", "tpa", "policy_no", "claim_no", "claimed_amount",
]


class Value(BaseModel):
    value: str
    confidence: float


class LineItem(BaseModel):
    description: str
    qty: str
    rate: str
    amount: str
    confidence: float


Fields = create_model("Fields", **{f: (Value, ...) for f in FIELDS})


class Extraction(BaseModel):
    document_type: str
    fields: Fields
    line_items: list[LineItem]


PROMPT = """You are reading an Indian hospital bill, pharmacy bill or health insurance claim form.
Extract the data exactly as printed. Do not calculate, correct or invent anything:
if the printed total is wrong, return the printed total.

- document_type: "bill", "claim_form" or "other".
- fields: for each field return the value as printed and a confidence from 0 to 1
  for how sure you are you read it correctly. If a field is not on the document,
  return value "" and confidence 1.
- Dates as DD-MM-YYYY. Amounts as plain numbers without currency symbols or commas.
- line_items: every charge row (room, tests, medicines, procedures...), in order,
  with qty, rate and amount as printed ("" if a column is absent) and a confidence.
- Do not put subtotal, tax, discount or total rows in line_items."""


def extract(data: bytes, mime_type: str, use_cache: bool = True) -> dict:
    """Return {"document_type", "fields": {name: {"value", "confidence"}}, "line_items": [...]}.

    Results are cached by file hash, so a demo bill seen once works offline.
    """
    cached = CACHE / f"{hashlib.sha256(data).hexdigest()}.json"
    if use_cache and cached.exists():
        return json.loads(cached.read_text())

    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=mime_type), PROMPT],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Extraction,
            temperature=0,
        ),
    )
    result = Extraction.model_validate_json(response.text).model_dump()

    CACHE.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result
