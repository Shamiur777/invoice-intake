"""Two extractors with the same output shape.

claude_extract:  sends the PDF to Claude and forces a structured tool call (the real pipeline).
baseline_extract: regex rules over the PDF text layer. No API needed. It is the baseline the
                  Claude extractor has to beat, and it keeps tests and demos runnable offline.
"""
import base64
import io
import os
import re
from datetime import datetime

from pypdf import PdfReader

from .schema import TOOL

MODEL = os.environ.get("INTAKE_MODEL", "claude-sonnet-5-5")

PROMPT = (
    "Extract the invoice data from this document by calling record_invoice. "
    "Use ISO dates (YYYY-MM-DD). For slash dates, assume day/month/year unless the document shows otherwise. "
    "If a field is missing or you are guessing, give it a low confidence. Never invent values."
)


def claude_extract(pdf_bytes: bytes, client=None) -> dict:
    import anthropic

    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode()}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise ValueError("model did not return a tool call")


# ---------------------------------------------------------------- baseline

def _num(s: str) -> float:
    return float(re.sub(r"[^0-9.]", "", s.replace(",", "")))


def _date(s: str) -> str:
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(s)


TOTAL_LABELS = {"subtotal": ("subtotal", "sub-total", "net"), "tax": ("tax", "vat/gst"),
                "total": ("total due", "total", "amount due")}


def baseline_extract(pdf_bytes: bytes) -> dict:
    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: dict = {}
    conf: dict = {}

    def put(field, fn):
        try:
            out[field] = fn()
            conf[field] = 0.9
        except Exception:
            out[field] = "" if field in ("vendor", "invoice_number", "invoice_date", "currency") else 0.0
            conf[field] = 0.0

    def find_after(prefixes):
        for l in lines:
            for p in prefixes:
                if l.lower().startswith(p.lower()):
                    return l[len(p):].strip()
        raise KeyError(prefixes)

    put("vendor", lambda: lines[0])
    put("invoice_number", lambda: find_after(["Invoice No:", "INVOICE #", "Ref"]))
    put("invoice_date", lambda: _date(find_after(["Date:", "Issued:", "Invoice date"])))

    def currency():
        for l in lines:
            m = re.search(r"All amounts in ([A-Z]{3})", l)
            if m:
                return m.group(1)
        blob = text
        for code, sym in (("AUD", "A$"), ("BDT", "BDT"), ("USD", "$")):
            if sym in blob or code in blob:
                return code
        raise KeyError("currency")
    put("currency", currency)

    def total_of(field):
        for l in lines:
            low = l.lower()
            for label in sorted(TOTAL_LABELS[field], key=len, reverse=True):
                if low.startswith(label):
                    rest = l[len(label):]
                    if re.search(r"\d", rest):
                        return _num(rest)
        # template 2 prints label and value on separate lines
        for i, l in enumerate(lines[:-1]):
            if l.lower() in TOTAL_LABELS[field] and re.search(r"\d", lines[i + 1]):
                return _num(lines[i + 1])
        raise KeyError(field)

    put("subtotal", lambda: total_of("subtotal"))
    out_tax = None
    try:
        out_tax = total_of("tax")
    except KeyError:
        out_tax = 0.0  # no tax line printed
    out["tax"], conf["tax"] = out_tax, 0.9
    put("total", lambda: total_of("total"))

    items = []
    try:
        start = next(i for i, l in enumerate(lines) if l.lower().startswith(("amount", "description"))) + 1
        while lines[start].lower() in ("qty", "unit price", "rate", "amount"):
            start += 1
        i = start
        while i + 3 < len(lines) and re.fullmatch(r"\d+", lines[i + 1]):
            items.append({"description": lines[i], "quantity": float(lines[i + 1]),
                          "unit_price": _num(lines[i + 2]), "amount": _num(lines[i + 3])})
            i += 4
    except Exception:
        items = []
    out["line_items"] = items
    out["confidence"] = conf
    return out
