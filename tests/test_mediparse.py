import copy
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.app as api
from backend.extract import FIELDS
from backend.locate import locate
from backend.validate import amount, validate


def make_doc(items=(("Room rent", "2", "1500", "3000"), ("CBC test", "1", "450", "450")),
             **values):
    base = {"patient_name": "Ravi Kumar", "hospital_name": "City Care Hospital",
            "bill_date": "10-10-2026", "subtotal": "3450", "tax": "0", "total": "3450"}
    base.update(values)
    return {
        "document_type": "bill",
        "fields": {f: {"value": base.get(f, ""), "confidence": 0.95} for f in FIELDS},
        "line_items": [{"description": d, "qty": q, "rate": r, "amount": a, "confidence": 0.95}
                       for d, q, r, a in items],
    }


def rules(doc):
    return sorted(i["rule"] for i in validate(doc))


def test_amount_parsing():
    assert amount("₹1,23,456.50") == 123456.5
    assert amount("Rs. 450/-") == 450
    assert amount("") is None and amount(None) is None


def test_clean_bill_passes():
    assert validate(make_doc()) == []


def test_wrong_total_is_caught():
    issues = validate(make_doc(total="5200"))
    assert [i["rule"] for i in issues] == ["total_math"]
    assert "5,200.00" in issues[0]["message"]


def test_items_not_matching_subtotal():
    assert rules(make_doc(subtotal="4000", total="4000")) == ["items_sum"]


def test_discount_and_tax():
    assert validate(make_doc(discount="450", tax="150", total="3150")) == []


def test_line_math_missing_field_duplicate_and_low_confidence():
    doc = make_doc(items=(("Paracetamol", "10", "2", "25"), ("Paracetamol", "10", "2", "25")),
                   patient_name="", subtotal="50", total="50")
    doc["fields"]["hospital_name"]["confidence"] = 0.4
    assert rules(doc) == ["duplicate", "line_math", "line_math", "low_confidence", "required"]


def test_rounding_tolerance():
    assert validate(make_doc(total="3450.60")) == []


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DB", tmp_path / "test.db")
    monkeypatch.setattr(api, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(api, "extract", lambda data, mime: copy.deepcopy(make_doc(total="5200")))
    return TestClient(api.app)


def test_upload_review_correct_export(client):
    r = client.post("/upload", files={"file": ("bill.jpg", b"fake-image", "image/jpeg")})
    assert r.status_code == 200 and r.json()["status"] == "review"
    bill_id = r.json()["id"]

    assert client.get("/bills/1/file").content == b"fake-image"
    assert client.get("/bills", params={"status": "review"}).json()[0]["issue_count"] == 1

    r = client.patch(f"/bills/{bill_id}", json={"field": "total", "value": "3450"})
    assert r.json()["status"] == "approved"
    assert client.patch(f"/bills/{bill_id}", json={"field": "../etc", "value": "x"}).status_code == 422

    with api.db() as conn:
        fix = conn.execute("SELECT ai_value, corrected_value FROM corrections").fetchone()
    assert tuple(fix) == ("5200", "3450")

    assert client.get("/export", params={"format": "csv"}).text.splitlines()[1].startswith("1,bill.jpg,approved")
    assert client.get("/export").content[:2] == b"PK"  # xlsx is a zip
    assert client.get("/export", params={"format": "json"}).json()[0]["data"]["fields"]["total"]["value"] == "3450"


def test_rejects_bad_type(client):
    assert client.post("/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract not installed")
def test_click_to_source_on_demo_bill():
    root = Path(__file__).resolve().parent.parent / "data"
    doc = json.loads((root / "truth" / "bill_03.json").read_text())
    boxes = locate((root / "samples" / "bill_03.png").read_bytes(), doc)
    assert boxes["total"][0] > 0.7 and boxes["total"][1] > boxes["subtotal"][1]  # bottom right, below subtotal
    assert boxes["line_items.3"][1] > boxes["line_items.1"][1]  # the repeated medicine gets its own row
