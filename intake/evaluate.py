"""Score an extractor against ground truth.

Reports per-field accuracy, how many invoices were auto-approved vs sent to review, and the accuracy
of the auto-approved set (the number that matters: wrong data that skips review is the costly error).

  python -m intake.evaluate baseline [invoices|hard]
  python -m intake.evaluate claude [invoices|hard]     # needs ANTHROPIC_API_KEY
"""
import json
import sys
from pathlib import Path

from .extract import baseline_extract, claude_extract
from .review import needs_review
from .schema import FIELDS

DATA = Path("data/invoices")  # override with --set hard


def same(field, a, b) -> bool:
    if field in ("subtotal", "tax", "total"):
        return abs(float(a) - float(b)) <= 0.01
    return str(a).strip().casefold() == str(b).strip().casefold()


def items_match(pred, truth) -> bool:
    if len(pred) != len(truth):
        return False
    return all(
        p["description"].strip().casefold() == t["description"].strip().casefold()
        and abs(p["amount"] - t["amount"]) <= 0.01 and abs(p["quantity"] - t["quantity"]) <= 0.01
        for p, t in zip(pred, truth)
    )


def invoice_correct(pred, truth) -> bool:
    return all(same(f, pred[f], truth[f]) for f in FIELDS) and items_match(pred["line_items"], truth["line_items"])


def evaluate(extractor, limit=None, data: Path = DATA) -> dict:
    truth = json.loads((data / "ground_truth.json").read_text(encoding="utf-8"))[:limit]
    field_hits = {f: 0 for f in FIELDS + ["line_items"]}
    auto_ok = auto_n = review_n = 0
    failures = []
    for t in truth:
        try:
            pred = extractor((data / t["file"]).read_bytes())
        except Exception as e:  # an extraction error is a review case, not a crash
            review_n += 1
            failures.append((t["file"], f"error: {e}"))
            continue
        for f in FIELDS:
            field_hits[f] += same(f, pred[f], t[f])
        field_hits["line_items"] += items_match(pred["line_items"], t["line_items"])
        correct = invoice_correct(pred, t)
        if needs_review(pred):
            review_n += 1
        else:
            auto_n += 1
            auto_ok += correct
            if not correct:
                failures.append((t["file"], "AUTO-APPROVED BUT WRONG"))
    n = len(truth)
    return {
        "invoices": n,
        "field_accuracy": {f: round(v / n, 3) for f, v in field_hits.items()},
        "auto_approved": auto_n,
        "sent_to_review": review_n,
        "auto_approved_accuracy": round(auto_ok / auto_n, 3) if auto_n else None,
        "silent_errors": [f for f in failures if "AUTO" in f[1]],
    }


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    folder = Path("data") / (sys.argv[2] if len(sys.argv) > 2 else "invoices")
    fn = {"baseline": baseline_extract, "claude": claude_extract}[which]
    print(json.dumps(evaluate(fn, data=folder), indent=2))
