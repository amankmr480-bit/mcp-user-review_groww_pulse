"""
Phase 5 — primary frontend (Streamlit): same layout as the former Phase 6 Next.js UI.
Pipeline runs in-process; no Vercel or separate FastAPI required for this UI.
"""

from __future__ import annotations

import json
from datetime import date

import streamlit as st

from pipeline import (
    get_email_draft,
    get_note,
    list_weeks,
    run_pipeline,
    send_email,
    week_info_from_date,
    week_info_from_week_id,
)

st.set_page_config(
    page_title="GROWW Review AI",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(160deg, #0f172a 0%, #1e3a8a 42%, #3b82f6 78%, #93c5fd 100%);
        background-attachment: fixed;
    }
    [data-testid="stHeader"] { background: rgba(15, 23, 42, 0.2); }
    .block-container { max-width: 1100px; padding-top: 1.5rem; }
    .p6-hero h1 {
        color: #f8fafc !important;
        text-shadow: 0 1px 2px rgba(15, 23, 42, 0.35);
        font-size: 1.75rem;
        margin-bottom: 0.25rem;
    }
    .p6-hero p { color: #e2e8f0 !important; margin-top: 0; }
    section.main div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.96) !important;
        border: 1px solid rgba(255, 255, 255, 0.5) !important;
        border-radius: 12px !important;
        box-shadow: 0 10px 40px rgba(15, 23, 42, 0.2) !important;
    }
    .p6-hint { font-size: 0.9rem; color: #334155; margin-top: 0.5rem; }
</style>
    """,
    unsafe_allow_html=True,
)


def _on_date_changed() -> None:
    st.session_state.gen_week_select = "—"


def _on_generated_week_changed() -> None:
    w = st.session_state.get("gen_week_select")
    if w and w != "—":
        try:
            info = week_info_from_week_id(w)
            st.session_state.ref_day_input = date.fromisoformat(info["week_beginning"])
        except ValueError:
            pass


if "ref_day_input" not in st.session_state:
    st.session_state.ref_day_input = date.today()
if "gen_week_select" not in st.session_state:
    st.session_state.gen_week_select = "—"
if "status_msg" not in st.session_state:
    st.session_state.status_msg = ""
if "status_ok" not in st.session_state:
    st.session_state.status_ok = True

st.markdown('<div class="p6-hero">', unsafe_allow_html=True)
st.markdown("# GROWW Review AI Frontend")
st.markdown(
    "<p>Streamlit (Phase 5). Pipeline runs in-process — no Vercel or separate API server required.</p>",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

weeks = list_weeks()
_gen_opts = ["—"] + weeks
if st.session_state.gen_week_select not in _gen_opts:
    st.session_state.gen_week_select = "—"

with st.container(border=True):
    st.subheader("Pipeline Controls")
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 0.9, 1])

    with c1:
        st.caption("Week — any day in that week (YYYY-MM-DD)")
        st.date_input(
            "week_date",
            key="ref_day_input",
            label_visibility="collapsed",
            on_change=_on_date_changed,
        )
        ref_day: date = st.session_state.ref_day_input
        info = week_info_from_date(ref_day.isoformat())
        st.markdown(
            f'<p class="p6-hint">ISO week <strong>{info["week_id"]}</strong> — Monday '
            f'<strong>{info["week_beginning"]}</strong></p>',
            unsafe_allow_html=True,
        )

    with c2:
        st.caption("Or choose a generated week")
        st.selectbox(
            "gen_week",
            options=_gen_opts,
            key="gen_week_select",
            label_visibility="collapsed",
            on_change=_on_generated_week_changed,
        )

    with c3:
        batch_size = st.number_input("Phase 2 batch size", min_value=1, max_value=200, value=15, step=1)

    with c4:
        run_ingest = st.checkbox("Run Phase 1 ingest", value=False)

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        run_clicked = st.button("Run Pipeline", type="primary", use_container_width=True)
    with b2:
        refresh_clicked = st.button("Refresh Weeks", use_container_width=True)
    with b3:
        reload_clicked = st.button("Reload Note & Draft", use_container_width=True)
    with b4:
        send_clicked = st.button("Send To Alias", use_container_width=True)

week_id = info["week_id"]
can_load = bool(week_id)

if st.session_state.status_msg:
    if st.session_state.status_ok:
        st.success(st.session_state.status_msg)
    else:
        st.error(st.session_state.status_msg)

if run_clicked:
    st.session_state.status_msg = ""
    with st.spinner("Running pipeline..."):
        result = run_pipeline(
            week=None,
            week_start_date=ref_day.isoformat(),
            run_ingest=run_ingest,
            batch_size=int(batch_size),
        )
    if result.get("ok"):
        st.session_state.status_msg = "Pipeline run completed."
        st.session_state.status_ok = True
    else:
        st.session_state.status_msg = f"Pipeline failed: {result}"
        st.session_state.status_ok = False
    st.rerun()

if refresh_clicked:
    st.session_state.status_msg = ""
    st.session_state.status_ok = True
    st.rerun()

if reload_clicked:
    st.session_state.status_msg = ""
    st.session_state.status_ok = True
    st.rerun()

if send_clicked and can_load:
    with st.spinner("Sending email..."):
        result = send_email(week_id)
    if result.get("ok"):
        st.session_state.status_msg = result.get("stdout", "Email sent successfully.").strip() or "Email sent successfully."
        st.session_state.status_ok = True
    else:
        st.session_state.status_msg = result.get("stderr", "Email send failed.") or "Email send failed."
        st.session_state.status_ok = False
    st.rerun()

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.subheader("Weekly Note")
        try:
            note = get_note(week_id)
            st.caption(f"Word count: {note.get('word_count', 'N/A')}")
            st.markdown(note.get("content", ""))
            with st.expander("Raw note JSON"):
                st.code(json.dumps(note, indent=2, ensure_ascii=False), language="json")
        except FileNotFoundError:
            st.caption("No note loaded.")

with col2:
    with st.container(border=True):
        st.subheader("Email Draft")
        try:
            draft = get_email_draft(week_id)
            st.markdown(f"**Subject:** {draft.get('subject', '')}")
            st.markdown(f"**Recipient:** {draft.get('recipient') or 'N/A'}")
            st.text(draft.get("body", ""))
        except FileNotFoundError:
            st.caption("No draft loaded.")
