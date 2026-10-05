# Invoice Intake

Upload invoice PDFs. An AI extractor reads each one and returns structured data. Clean extractions are auto-approved; anything doubtful goes to a human review queue. Approved data exports to CSV.

All invoices in this repo are synthetic. Every vendor is fictional.

## The problem
Finance teams re-type invoice data by hand. Full automation is risky, because a confidently wrong extraction can end up in the books. The useful design is: automate the easy ones, route the doubtful ones to a person, and never let wrong data skip review.

## How it works

```
PDF -> extractor (Claude or regex baseline) -> structured record + per-field confidence
    -> review rules -> AUTO-APPROVED  or  REVIEW QUEUE (with reasons) -> CSV
```

- `intake/extract.py`: `claude_extract` sends the PDF to Claude and forces a structured tool call. `baseline_extract` uses regex over the PDF text layer. It is the baseline Claude has to beat, and it keeps the project runnable without an API key.
- `intake/review.py`: sends a record to review if any field has low confidence **or** the arithmetic fails (line items must sum to the subtotal, quantity x price must equal the line amount, subtotal + tax must equal the total). The arithmetic checks do not depend on the model, so a confident but wrong extraction is still caught.
- `intake/evaluate.py`: scores any extractor against ground truth. Reports per-field accuracy, review rate, and the accuracy of the auto-approved set.
- `app.py`: Streamlit UI with the review queue and CSV export.

## Test data
- `data/invoices`: 50 clean invoices in 3 layouts, different date formats and currencies (USD, AUD, BDT), some without a tax line.
- `data/hard`: 20 harder invoices. 10 are image-only scans (rotated, noisy, no text layer) and 10 use unfamiliar labels ("Bill from", "Document no.", "Payable").

Regenerate with `python -m intake.generate`.

## Results

| Extractor | Set | Field accuracy | Auto-approved | Silent errors |
|---|---|---|---|---|
| Regex baseline | clean (50) | 100% on every field | 50 | 0 |
| Regex baseline | hard (20) | 0-50% by field | 0 (all 20 sent to review) | 0 |
| Claude | clean (50) | *not run yet* | | |
| Claude | hard (20) | *not run yet* | | |

The baseline scores 100% on the clean set because its rules were written for those layouts, so that number says nothing about real-world performance. The hard set is the fair comparison. On it the baseline fails, but the review rules send all 20 to a human instead of approving wrong data, so there are no silent errors.

Claude results: run the commands below, then paste the numbers in the table. I have not included any until they exist.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python -m pytest -q             # 7 tests, no API key needed

python -m intake.evaluate baseline hard
set ANTHROPIC_API_KEY=your-key  # Windows (use export on Mac/Linux)
python -m intake.evaluate claude hard
streamlit run app.py
```

The model defaults to `claude-sonnet-5-5`; override with the `INTAKE_MODEL` environment variable.

## Design decisions
- **Forced tool call for output**: guarantees valid JSON matching the schema, with no text parsing.
- **Per-field confidence from the model plus independent arithmetic checks**: model confidence alone is not trustworthy.
- **Errors count as review cases, not crashes**: one bad file never stops a batch.
- **Baseline kept in the repo**: shows what AI adds over rules, and keeps tests offline.

## Limits and next steps
- Synthetic data only. Real invoices vary far more (handwriting, multi-page, multiple currencies on one document).
- Add duplicate detection (same vendor and invoice number).
- Add a feedback loop: log human corrections and measure which fields need prompt changes.
- Deploy to Hugging Face Spaces or Streamlit Community Cloud.
