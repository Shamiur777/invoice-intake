"""Invoice schema shared by the extractors, the review rules and the evaluator."""

FIELDS = ["vendor", "invoice_number", "invoice_date", "currency", "subtotal", "tax", "total"]

TOOL = {
    "name": "record_invoice",
    "description": "Record the data extracted from an invoice, with a 0-1 confidence for each field.",
    "input_schema": {
        "type": "object",
        "properties": {
            "vendor": {"type": "string", "description": "Name of the company issuing the invoice."},
            "invoice_number": {"type": "string"},
            "invoice_date": {"type": "string", "description": "ISO format YYYY-MM-DD."},
            "currency": {"type": "string", "description": "ISO 4217 code, e.g. USD, AUD, BDT."},
            "subtotal": {"type": "number"},
            "tax": {"type": "number", "description": "0 if the invoice shows no tax."},
            "total": {"type": "number", "description": "Final amount due."},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit_price": {"type": "number"},
                        "amount": {"type": "number"},
                    },
                    "required": ["description", "quantity", "unit_price", "amount"],
                },
            },
            "confidence": {
                "type": "object",
                "description": "Confidence from 0 to 1 for each of the fields above. Use a low value when text is "
                               "ambiguous, missing or you had to guess.",
                "properties": {f: {"type": "number"} for f in FIELDS},
                "required": FIELDS,
            },
        },
        "required": FIELDS + ["line_items", "confidence"],
    },
}
