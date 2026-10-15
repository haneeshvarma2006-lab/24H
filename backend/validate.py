"""Rule checks that catch the AI's mistakes (and the hospital's). No ML here."""
import re

TOLERANCE = 1.0  # rupees, for rounding on printed bills
MIN_CONFIDENCE = 0.8
REQUIRED = ["patient_name", "hospital_name", "bill_date", "total"]


def amount(text):
    """'₹1,23,456.50' -> 123456.5, 'Rs. 450/-' -> 450.0; None if there is no number."""
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(text or ""))
    return float(match.group().replace(",", "")) if match else None


def validate(doc: dict) -> list[dict]:
    """Return a list of issues: {"field", "rule", "message"}. Empty list means approved."""
    issues = []

    def flag(field, rule, message):
        issues.append({"field": field, "rule": rule, "message": message})

    fields = {name: f["value"] for name, f in doc["fields"].items()}
    items = doc["line_items"]

    if doc.get("document_type") == "claim_form":
        required = ["patient_name", "policy_no", "claimed_amount"]
    else:
        required = REQUIRED
    for name in required:
        if not str(fields.get(name) or "").strip():
            flag(name, "required", f"{name.replace('_', ' ').capitalize()} is missing")

    seen = set()
    for i, item in enumerate(items):
        qty, rate, amt = amount(item["qty"]), amount(item["rate"]), amount(item["amount"])
        if None not in (qty, rate, amt) and abs(qty * rate - amt) > TOLERANCE:
            flag(f"line_items.{i}.amount", "line_math",
                 f"'{item['description']}': {qty:g} × {rate:,.2f} = {qty * rate:,.2f}, bill says {amt:,.2f}")
        key = (item["description"].strip().lower(), amt)
        if amt is not None and key in seen:  # rows without an amount (blank lines, headers) are not double charges
            flag(f"line_items.{i}", "duplicate", f"Duplicate line item: '{item['description']}' ({amt:,.2f})")
        seen.add(key)

    item_sum = sum(a for a in (amount(i["amount"]) for i in items) if a is not None)
    if not items and doc.get("document_type") == "bill" and (fields.get("subtotal") or fields.get("total")):
        flag("subtotal", "items_sum", "No line items were read from this bill, so the total cannot be checked")
    subtotal, total = amount(fields.get("subtotal")), amount(fields.get("total"))
    discount = abs(amount(fields.get("discount")) or 0)
    tax = amount(fields.get("tax")) or 0

    if items and subtotal is not None and abs(item_sum - subtotal) > TOLERANCE:
        flag("subtotal", "items_sum",
             f"Line items add up to ₹{item_sum:,.2f} but subtotal says ₹{subtotal:,.2f}")
    base = subtotal if subtotal is not None else (item_sum if items else None)
    if base is not None and total is not None and abs(base - discount + tax - total) > TOLERANCE:
        flag("total", "total_math",
             f"₹{base:,.2f} − discount ₹{discount:,.2f} + tax ₹{tax:,.2f} = ₹{base - discount + tax:,.2f}, "
             f"but total says ₹{total:,.2f}")

    for name, f in doc["fields"].items():
        if str(f["value"]).strip() and f["confidence"] < MIN_CONFIDENCE:
            flag(name, "low_confidence", f"AI is only {f['confidence']:.0%} sure it read {name.replace('_', ' ')} correctly")
    for i, item in enumerate(items):
        if item["confidence"] < MIN_CONFIDENCE:
            flag(f"line_items.{i}", "low_confidence",
                 f"AI is only {item['confidence']:.0%} sure it read line '{item['description']}' correctly")

    return issues
