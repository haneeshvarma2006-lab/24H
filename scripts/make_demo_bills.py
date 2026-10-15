"""Render fictitious demo bills (PNG) + their correct values (truth JSON in the extraction schema).

python scripts/make_demo_bills.py      # needs Chromium; writes data/samples/ and data/truth/
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.extract import FIELDS  # noqa: E402

CHROME = os.environ.get("CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
W, H = 900, 1200

HOSPITAL = dict(hospital_name="Arogya Care Hospital", hospital_address="12 Gandhi Road, Tirupati 517501",
                doctor="Dr. S. Reddy")
PHARMACY = dict(hospital_name="Sanjeevani Medicals", hospital_address="4 Bazaar Street, Tirupati 517501",
                doctor="Dr. K. Rao")

# printed values; "mistake" says what is wrong on paper (validation must catch it)
BILLS = [
    dict(name="bill_01", style="hospital", mistake=None, **HOSPITAL,
         patient_name="Ravi Kumar", uhid="AC-20431", age="45", gender="Male", bill_no="INV-5521",
         bill_date="10-10-2026", admission_date="08-10-2026", discharge_date="10-10-2026",
         insurer="Star Health", policy_no="P-8812-7741",
         items=[("Room Rent (General Ward)", "2", "1500", "3000"), ("Doctor Consultation", "2", "500", "1000"),
                ("CBC Blood Test", "1", "450", "450"), ("Chest X-Ray", "1", "800", "800"),
                ("IV Fluids (NS 500ml)", "4", "120", "480")],
         subtotal="5730", discount="0", tax="0", total="5730"),
    dict(name="bill_02", style="hospital", mistake="total says 6,530; items add up to 5,730", **HOSPITAL,
         patient_name="Lakshmi Devi", uhid="AC-20517", age="62", gender="Female", bill_no="INV-5534",
         bill_date="11-10-2026", admission_date="09-10-2026", discharge_date="11-10-2026",
         insurer="", policy_no="",
         items=[("Room Rent (General Ward)", "2", "1500", "3000"), ("Doctor Consultation", "2", "500", "1000"),
                ("ECG", "1", "350", "350"), ("Lipid Profile", "1", "900", "900"),
                ("Nursing Charges", "2", "240", "480")],
         subtotal="5730", discount="0", tax="0", total="6530"),
    dict(name="bill_03", style="pharmacy", mistake="patient name missing; Pantoprazole billed twice", **PHARMACY,
         patient_name="", uhid="", age="", gender="", bill_no="SM-0912",
         bill_date="12-10-2026", admission_date="", discharge_date="", insurer="", policy_no="",
         items=[("Paracetamol 650mg (10 tabs)", "2", "32", "64"), ("Pantoprazole 40mg (15 tabs)", "1", "145", "145"),
                ("Amoxicillin 500mg (10 caps)", "1", "98", "98"), ("Pantoprazole 40mg (15 tabs)", "1", "145", "145"),
                ("ORS Sachet", "5", "22", "110")],
         subtotal="562", discount="28", tax="27", total="561"),
    dict(name="bill_04", style="pharmacy", mistake=None, **PHARMACY,
         patient_name="Meena Iyer", uhid="", age="34", gender="Female", bill_no="SM-0918",
         bill_date="13-10-2026", admission_date="", discharge_date="", insurer="", policy_no="",
         items=[("Azithromycin 500mg (3 tabs)", "1", "72", "72"), ("Cetirizine 10mg (10 tabs)", "1", "18", "18"),
                ("Cough Syrup 100ml", "2", "95", "190"), ("Vitamin C 500mg (15 tabs)", "1", "60", "60")],
         subtotal="340", discount="17", tax="16", total="339"),
]


def rupees(x):
    return f"{float(x):,.2f}"


def html(b):
    rows = "".join(f"<tr><td>{n}</td><td>{d}</td><td class=r>{q}</td><td class=r>{rupees(r)}</td>"
                   f"<td class=r>{rupees(a)}</td></tr>" for n, (d, q, r, a) in enumerate(b["items"], 1))
    if b["style"] == "hospital":
        head = f"""<div class=hosp><h1>{b['hospital_name']}</h1><p>{b['hospital_address']} · Ph: 0877-2200000</p></div>
        <h2>IN-PATIENT FINAL BILL</h2>
        <table class=meta><tr><td>Patient Name: <b>{b['patient_name']}</b></td><td>UHID: <b>{b['uhid']}</b></td></tr>
        <tr><td>Age / Gender: <b>{b['age']} / {b['gender']}</b></td><td>Bill No: <b>{b['bill_no']}</b></td></tr>
        <tr><td>Admission: <b>{b['admission_date']}</b></td><td>Discharge: <b>{b['discharge_date']}</b></td></tr>
        <tr><td>Consultant: <b>{b['doctor']}</b></td><td>Bill Date: <b>{b['bill_date']}</b></td></tr>
        <tr><td>Insurer: <b>{b['insurer'] or '-'}</b></td><td>Policy No: <b>{b['policy_no'] or '-'}</b></td></tr></table>"""
    else:
        head = f"""<div class=pharm><h1>{b['hospital_name']}</h1><p>{b['hospital_address']}<br>GSTIN 37ABCDE1234F1Z5 · DL No. 20/21-AP-1234</p></div>
        <h2>TAX INVOICE</h2>
        <table class=meta><tr><td>Bill No: <b>{b['bill_no']}</b></td><td>Date: <b>{b['bill_date']}</b></td></tr>
        <tr><td>Patient: <b>{b['patient_name']}</b></td><td>Age/Sex: <b>{b['age']} {b['gender']}</b></td></tr>
        <tr><td colspan=2>Prescribed by: <b>{b['doctor']}</b></td></tr></table>"""
    return f"""<html><head><style>
    body{{margin:0;width:{W}px;height:{H}px;font-family:'DejaVu Sans',Arial,sans-serif;font-size:17px;color:#111;background:#fff}}
    .page{{padding:40px 50px}} h1{{margin:0;font-size:32px}} h2{{text-align:center;font-size:20px;letter-spacing:2px;border:2px solid #111;padding:6px;margin:22px 0}}
    .hosp{{text-align:center;border-bottom:3px double #111;padding-bottom:10px}} .pharm{{border-left:8px solid #2a7;padding-left:14px}}
    table{{width:100%;border-collapse:collapse}} .meta td{{padding:5px 0;width:50%}}
    .items{{margin-top:20px}} .items th,.items td{{border:1px solid #444;padding:7px 8px}} .items th{{background:#eee;text-align:left}}
    .r{{text-align:right}} .tot{{width:45%;margin:18px 0 0 auto}} .tot td{{padding:5px 8px}} .grand td{{font-weight:bold;font-size:20px;border-top:2px solid #111}}
    .foot{{margin-top:60px;font-size:13px;color:#666;text-align:center}}
    </style></head><body><div class=page>{head}
    <table class=items><tr><th>#</th><th>Description</th><th class=r>Qty</th><th class=r>Rate (₹)</th><th class=r>Amount (₹)</th></tr>{rows}</table>
    <table class=tot><tr><td>Sub Total</td><td class=r>{rupees(b['subtotal'])}</td></tr>
    <tr><td>Discount</td><td class=r>{rupees(b['discount'])}</td></tr><tr><td>GST</td><td class=r>{rupees(b['tax'])}</td></tr>
    <tr class=grand><td>Net Payable</td><td class=r>₹ {rupees(b['total'])}</td></tr></table>
    <p class=foot>Demo document · fictitious data · not a real bill</p></div></body></html>"""


def truth(b):
    return {"document_type": "bill",
            "fields": {f: {"value": str(b.get(f, "")), "confidence": 1.0} for f in FIELDS},
            "line_items": [{"description": d, "qty": q, "rate": r, "amount": a, "confidence": 1.0}
                           for d, q, r, a in b["items"]],
            "mistake": b["mistake"]}


def main():
    samples, truths = ROOT / "data" / "samples", ROOT / "data" / "truth"
    samples.mkdir(parents=True, exist_ok=True)
    truths.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for b in BILLS:
            page, shot = Path(tmp) / f"{b['name']}.html", Path(tmp) / f"{b['name']}.png"
            page.write_text(html(b), encoding="utf-8")
            # headless Chrome eats ~90px of the window height, so render taller and crop
            subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                            f"--window-size={W},{H + 200}", f"--screenshot={shot}", page.as_uri()],
                           check=True, capture_output=True)
            Image.open(shot).crop((0, 0, W, H)).convert("RGB").save(samples / f"{b['name']}.png")
            (truths / f"{b['name']}.json").write_text(json.dumps(truth(b), indent=2, ensure_ascii=False))

    # a "phone photo" of bill_01: tilted, blurred, grey, JPEG
    photo = Image.open(samples / "bill_01.png").convert("L").rotate(3, expand=True, fillcolor=200)
    photo.filter(ImageFilter.GaussianBlur(1.1)).save(samples / "bill_05_photo.jpg", quality=55)
    (truths / "bill_05_photo.json").write_text((truths / "bill_01.json").read_text())
    print(f"wrote {len(BILLS) + 1} bills to {samples}")


if __name__ == "__main__":
    main()
