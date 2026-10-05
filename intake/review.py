"""Decide whether an extraction can be auto-approved or needs a human.

The model's own confidence is only one signal. Arithmetic checks run independently of the model,
so a confidently wrong extraction still gets caught when the numbers do not add up.
"""

CONFIDENCE_THRESHOLD = 0.85
TOLERANCE = 0.02


def review_reasons(result: dict, threshold: float = CONFIDENCE_THRESHOLD) -> list[str]:
    reasons = []
    conf = result.get("confidence") or {}
    for field, value in conf.items():
        if value < threshold:
            reasons.append(f"low confidence on {field} ({value:.2f})")

    items = result.get("line_items") or []
    if not items:
        reasons.append("no line items found")
    else:
        items_sum = sum(i["amount"] for i in items)
        if abs(items_sum - result["subtotal"]) > TOLERANCE:
            reasons.append(f"line items sum {items_sum:.2f} != subtotal {result['subtotal']:.2f}")
        for i in items:
            if abs(i["quantity"] * i["unit_price"] - i["amount"]) > TOLERANCE:
                reasons.append(f"line '{i['description'][:30]}' qty x price != amount")
    if abs(result["subtotal"] + result["tax"] - result["total"]) > TOLERANCE:
        reasons.append("subtotal + tax != total")
    return reasons


def needs_review(result: dict, threshold: float = CONFIDENCE_THRESHOLD) -> bool:
    return bool(review_reasons(result, threshold))
