"""
Phase 5 — product frontend (Streamlit): pipeline controls, weekly note, email draft.
Pipeline runs in-process; FastAPI in this package is optional for HTTP clients.
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
    r"""
<style id="groww-ui-overrides">
    /* Full-page gradient (overrides theme background) */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(160deg, #0f172a 0%, #1e3a8a 42%, #3b82f6 78%, #93c5fd 100%) !important;
        background-attachment: fixed !important;
        color: #ffffff !important;
    }
    [data-testid="stAppViewContainer"] > div:first-child {
        background: transparent !important;
    }
    [data-testid="stHeader"] { background: rgba(15, 23, 42, 0.25) !important; }
    [data-testid="stHeader"] button, [data-testid="stHeader"] span, [data-testid="stHeader"] a {
        color: #ffffff !important;
    }
    section.main .block-container {
        max-width: 1100px;
        padding-top: 1.5rem;
        color: #ffffff !important;
    }
    section.main a { color: #bfdbfe !important; }

    /* Hero title */
    .p6-hero, .p6-hero * { color: #ffffff !important; }
    .p6-hero h1 {
        text-shadow: 0 1px 2px rgba(15, 23, 42, 0.45);
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0 0 1rem 0;
        padding: 0;
        border: none;
    }

    /* Beat Streamlit Emotion default (#31333F): all body text in main = white */
    section.main p, section.main li, section.main ul, section.main ol,
    section.main h1, section.main h2, section.main h3, section.main h4, section.main h5, section.main h6,
    section.main label, section.main span:not(button span),
    section.main [data-testid="stCaption"],
    section.main [data-testid="stWidgetLabel"] p,
    section.main [data-testid="stWidgetLabel"] label,
    section.main [data-testid="stMarkdownContainer"],
    section.main [data-testid="stMarkdownContainer"] p,
    section.main [data-testid="stMarkdownContainer"] span,
    section.main [data-testid="stMarkdownContainer"] li,
    section.main [data-testid="stMarkdownContainer"] strong,
    section.main [data-testid="stMarkdownContainer"] em,
    section.main [data-testid="stMarkdownContainer"] code,
    section.main .stMarkdown p, section.main .stMarkdown li, section.main .stMarkdown span,
    section.main .stMarkdown strong, section.main .stMarkdown h1, section.main .stMarkdown h2,
    section.main .stMarkdown h3, section.main .stMarkdown h4,
    section.main [data-testid="stText"], section.main [data-testid="stText"] pre,
    section.main [data-testid="stExpander"] details, section.main [data-testid="stExpander"] summary,
    section.main [data-testid="stExpander"] p, section.main [data-testid="stExpander"] span,
    section.main [data-testid="stCheckbox"] label, section.main [data-testid="stCheckbox"] span,
    section.main [data-testid="stSpinner"] p,
    section.main [data-testid="stAlert"] p, section.main [data-testid="stAlert"] div,
    section.main [data-testid="stNotification"] p {
        color: #ffffff !important;
    }

    /* Emotion wrapper divs (Streamlit 1.28+) */
    section.main [class*="st-emotion-cache"] {
        color: #ffffff !important;
    }

    /* Glass panels */
    section.main div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(15, 23, 42, 0.5) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3) !important;
    }

    .p6-hint, .p6-hint strong {
        font-size: 0.9rem;
        color: #ffffff !important;
        margin-top: 0.5rem;
    }

    /* --- Exceptions: keep inputs/selects readable (dark text on light field) --- */
    section.main [data-baseweb="select"] *,
    section.main [data-baseweb="input"] input,
    section.main input[type="text"], section.main input[type="number"],
    section.main [data-testid="stDateInput"] input,
    section.main [data-testid="stNumberInput"] input {
        color: #0f172a !important;
    }
    section.main [data-baseweb="select"] > div,
    section.main [data-baseweb="input"] input,
    section.main [data-testid="stDateInput"] input,
    section.main [data-testid="stNumberInput"] input {
        background-color: #f8fafc !important;
    }
    /* Select displayed value: Streamlit nests spans inside control */
    section.main [data-baseweb="select"] [class*="css-"] {
        color: #0f172a !important;
    }

    /* Secondary buttons: dark label on light button */
    section.main button[kind="secondary"], section.main [data-testid="baseButton-secondary"] {
        color: #0f172a !important;
        background-color: #f1f5f9 !important;
        border: 1px solid rgba(255, 255, 255, 0.35) !important;
    }

    /* JSON / code in expander */
    section.main [data-testid="stCodeBlock"] code, section.main [data-testid="stCodeBlock"] pre {
        color: #e2e8f0 !important;
        background: rgba(0, 0, 0, 0.35) !important;
    }
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

st.markdown(
    '<div class="p6-hero"><h1>GROWW Review AI Frontend</h1></div>',
    unsafe_allow_html=True,
)

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
        st.caption("Or choose a generated week_id")
        st.selectbox(
            "gen_week",
            options=_gen_opts,
            key="gen_week_select",
            label_visibility="collapsed",
            format_func=lambda x: "(none yet)" if x == "—" else x,
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
        err = result.get("pipeline_error")
        st.session_state.status_msg = err if err else f"Pipeline failed: {result}"
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
