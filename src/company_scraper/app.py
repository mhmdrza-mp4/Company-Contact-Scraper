"""Streamlit web app for the scraper."""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

import sys
from pathlib import Path

_src = str(Path(__file__).resolve().parent.parent)
if _src not in sys.path:
    sys.path.insert(0, _src)

from company_scraper import config
from company_scraper.scraper import (
    deduplicate_urls,
    scrape_company,
    reset_rate_limiter,
    run_scrape,
)

st.set_page_config(page_title="Company Contact Scraper", layout="wide")
st.title("Company Contact Info Scraper")
st.write(
    "Provide company URLs either by pasting them below or uploading a "
    ".txt file (one URL per line)."
)

# --- Sidebar settings (stored in session_state) ---
st.sidebar.header("Scraper Settings")

if "request_timeout" not in st.session_state:
    st.session_state.request_timeout = config.REQUEST_TIMEOUT
if "max_retries" not in st.session_state:
    st.session_state.max_retries = config.MAX_RETRIES
if "retry_delay" not in st.session_state:
    st.session_state.retry_delay = config.RETRY_DELAY
if "max_workers" not in st.session_state:
    st.session_state.max_workers = config.MAX_WORKERS

st.session_state.request_timeout = st.sidebar.slider(
    "Request timeout (seconds)",
    min_value=3,
    max_value=30,
    value=st.session_state.request_timeout,
    help="How long to wait for a website to respond before giving up.",
)

st.session_state.max_retries = st.sidebar.slider(
    "Max retries per site",
    min_value=1,
    max_value=6,
    value=st.session_state.max_retries,
    help="How many times to retry a failed request before marking it as failed.",
)

st.session_state.retry_delay = st.sidebar.slider(
    "Delay between retries (seconds)",
    min_value=0,
    max_value=10,
    value=st.session_state.retry_delay,
    help="Pause between retry attempts.",
)

st.session_state.max_workers = st.sidebar.slider(
    "Parallel workers",
    min_value=1,
    max_value=20,
    value=st.session_state.max_workers,
    help="Number of websites processed at the same time. Higher = faster, but "
    "more likely to trigger rate limits.",
)

st.sidebar.divider()
st.sidebar.caption(
    "Changes here apply only to this session and don't modify config.py."
)

# --- Input section ---
col1, col2 = st.columns(2)

with col1:
    pasted_text = st.text_area("Paste URLs (one per line)", height=250)

with col2:
    uploaded_file = st.file_uploader("...or upload a .txt file", type=["txt"])

raw_urls: list[str] = []

if pasted_text.strip():
    raw_urls.extend(pasted_text.strip().splitlines())

if uploaded_file is not None:
    content = uploaded_file.read().decode("utf-8")
    raw_urls.extend(content.strip().splitlines())

urls = deduplicate_urls(raw_urls)

if raw_urls:
    st.info(f"{len(raw_urls)} URLs provided, {len(urls)} unique after removing duplicates.")

# --- Max URL limit ---
if len(urls) > config.MAX_URLS_STREAMLIT:
    st.error(
        f"Too many URLs: {len(urls)} provided, but the limit is "
        f"{config.MAX_URLS_STREAMLIT}. Please reduce the list."
    )
    st.stop()

# --- Run ---
if st.button("Start scraping", disabled=(len(urls) == 0)):
    progress_bar = st.progress(0)
    status_text = st.empty()

    reset_rate_limiter()

    def _progress(completed: int, total: int) -> None:
        progress_bar.progress(completed / total)
        if completed > 0:
            status_text.text(f"Processed {completed}/{total}")

    results = run_scrape(
        urls,
        max_workers=st.session_state.max_workers,
        timeout=st.session_state.request_timeout,
        max_retries=st.session_state.max_retries,
        progress_callback=_progress,
    )

    status_text.text("Done.")

    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)

    # Prepare Excel for download
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Companies")
    buffer.seek(0)

    st.download_button(
        label="Download results as Excel",
        data=buffer,
        file_name=config.OUTPUT_EXCEL,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
