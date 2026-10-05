"""Streamlit UI: upload invoices, auto-approve the clean ones, review the rest, export CSV."""
import os

import pandas as pd
import streamlit as st

from intake.extract import baseline_extract, claude_extract
from intake.review import CONFIDENCE_THRESHOLD, review_reasons

st.set_page_config(page_title="Invoice Intake", layout="wide")
st.title("Invoice Intake")
st.caption("Upload invoice PDFs. Clean extractions are auto-approved; anything doubtful goes to a human.")

has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
engine = st.sidebar.radio("Extractor", ["Claude", "Baseline (regex, offline)"], index=0 if has_key else 1)
threshold = st.sidebar.slider("Confidence threshold", 0.5, 1.0, CONFIDENCE_THRESHOLD, 0.05)
if engine == "Claude" and not has_key:
    st.sidebar.error("Set ANTHROPIC_API_KEY to use Claude.")

files = st.file_uploader("Invoices (PDF)", type="pdf", accept_multiple_files=True)

if files and not (engine == "Claude" and not has_key):
    extractor = claude_extract if engine == "Claude" else baseline_extract
    rows = []
    for f in files:
        try:
            res = extractor(f.getvalue())
            reasons = review_reasons(res, threshold)
        except Exception as e:
            res, reasons = {}, [f"extraction failed: {e}"]
        rows.append({"file": f.name, "status": "REVIEW" if reasons else "AUTO-APPROVED",
                     "why": "; ".join(reasons), **{k: res.get(k) for k in
                     ["vendor", "invoice_number", "invoice_date", "currency", "subtotal", "tax", "total"]}})
    df = pd.DataFrame(rows)
    ok = df[df.status == "AUTO-APPROVED"]
    c1, c2 = st.columns(2)
    c1.metric("Auto-approved", len(ok))
    c2.metric("Needs review", len(df) - len(ok))

    st.subheader("Review queue")
    queue = df[df.status == "REVIEW"].drop(columns="status")
    fixed = st.data_editor(queue, key="queue", use_container_width=True, hide_index=True) if len(queue) else queue
    if not len(queue):
        st.success("Nothing to review.")

    st.subheader("Approved")
    st.dataframe(ok.drop(columns=["status", "why"]), use_container_width=True, hide_index=True)

    final = pd.concat([ok.drop(columns=["status", "why"]), fixed.drop(columns="why", errors="ignore")])
    st.download_button("Download all as CSV", final.to_csv(index=False), "invoices.csv", "text/csv")
