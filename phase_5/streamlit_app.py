"""
Phase 5 Streamlit backend UI:
- trigger pipeline (ingest -> analyze -> note)
- inspect generated notes and drafts
- send draft to alias
"""

from __future__ import annotations

import json

import streamlit as st

from datetime import date

from pipeline import get_email_draft, get_note, list_weeks, run_pipeline, send_email, week_info_from_date


st.set_page_config(page_title="GROWW Review AI Backend", layout="wide")
st.title("GROWW Review AI - Backend Console (Phase 5)")

st.markdown("Run pipeline stages and manage weekly notes/email drafts.")

with st.sidebar:
    st.header("Run Options")
    ref_day = st.date_input(
        "Week — pick any day (YYYY-MM-DD)",
        value=date.today(),
        help="ISO week is derived from this calendar day (same as Phase 1 ingest).",
    )
    info = week_info_from_date(ref_day.isoformat())
    st.caption(f"ISO week **{info['week_id']}** — week begins Monday **{info['week_beginning']}**")
    run_ingest = st.checkbox("Run Phase 1 ingest before analysis", value=False)
    batch_size = st.number_input("Phase 2 batch size", min_value=1, max_value=200, value=15, step=1)
    if st.button("Run Pipeline (Phase 2 -> Phase 3)", use_container_width=True):
        with st.spinner("Running pipeline..."):
            result = run_pipeline(
                week=None,
                week_start_date=ref_day.isoformat(),
                run_ingest=run_ingest,
                batch_size=int(batch_size),
            )
        if result.get("ok"):
            st.success("Pipeline run completed successfully.")
        else:
            st.error("Pipeline failed.")
        st.json(result)

st.subheader("Available Weeks")
weeks = list_weeks()
if not weeks:
    st.info("No Phase 3 outputs found yet. Run the pipeline first.")
    st.stop()

week = st.selectbox("Select week", weeks, index=len(weeks) - 1)

col1, col2 = st.columns(2)
with col1:
    st.markdown("### Weekly Note")
    note = get_note(week)
    st.markdown(note.get("content", ""))
    with st.expander("Raw note JSON"):
        st.code(json.dumps(note, indent=2, ensure_ascii=False), language="json")

with col2:
    st.markdown("### Email Draft")
    draft = get_email_draft(week)
    st.text_input("Subject", value=draft.get("subject", ""), disabled=True)
    st.text_area("Body", value=draft.get("body", ""), height=350, disabled=True)
    st.text_input("Recipient", value=draft.get("recipient", ""), disabled=True)
    if st.button("Send To Alias", use_container_width=True):
        with st.spinner("Sending email..."):
            result = send_email(week)
        if result.get("ok"):
            st.success(result.get("stdout", "Email sent"))
        else:
            st.error(result.get("stderr", "Email send failed"))
        with st.expander("Send result"):
            st.json(result)

