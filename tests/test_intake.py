import json
from pathlib import Path
from types import SimpleNamespace

from intake.evaluate import evaluate, invoice_correct
from intake.extract import baseline_extract, claude_extract
from intake.review import review_reasons

DATA = Path("data/invoices")
TRUTH = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))


def good():
    return {"vendor": "X", "invoice_number": "1", "invoice_date": "2026-01-01", "currency": "USD",
            "subtotal": 100.0, "tax": 10.0, "total": 110.0,
            "line_items": [{"description": "a", "quantity": 2, "unit_price": 50.0, "amount": 100.0}],
            "confidence": {k: 0.95 for k in ["vendor", "invoice_number", "invoice_date", "currency",
                                              "subtotal", "tax", "total"]}}


def test_clean_extraction_is_auto_approved():
    assert review_reasons(good()) == []


def test_low_confidence_goes_to_review():
    r = good(); r["confidence"]["total"] = 0.4
    assert any("total" in x for x in review_reasons(r))


def test_confident_but_wrong_arithmetic_is_caught():
    r = good(); r["total"] = 150.0  # model is "confident" but numbers do not add up
    assert "subtotal + tax != total" in review_reasons(r)


def test_line_items_must_match_subtotal():
    r = good(); r["line_items"][0]["amount"] = 90.0
    assert any("line items sum" in x for x in review_reasons(r))


def test_baseline_reads_a_standard_invoice():
    t = TRUTH[0]
    assert invoice_correct(baseline_extract((DATA / t["file"]).read_bytes()), t)


def test_baseline_never_silently_approves_wrong_data_on_hard_set():
    res = evaluate(baseline_extract, data=Path("data/hard"))
    assert res["silent_errors"] == []


def test_claude_extract_returns_tool_input_from_response():
    payload = good()
    fake = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=payload)])))
    assert claude_extract(b"%PDF-fake", client=fake) == payload
