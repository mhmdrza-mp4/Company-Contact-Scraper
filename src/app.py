import io
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

import config
from scraper import scrape_company, deduplicate_urls

st.set_page_config(page_title="Company Contact Scraper", layout="wide")
st.title("Company Contact Info Scraper")
st.write("Provide company URLs either by pasting them below or uploading a .txt file (one URL per line).")

# --- Sidebar: adjustable settings (override config.py defaults at runtime) ---
st.sidebar.header("Scraper Settings")

request_timeout = st.sidebar.slider(
    "Request timeout (seconds)", min_value=3, max_value=30,
    value=config.REQUEST_TIMEOUT,
    help="How long to wait for a website to respond before giving up."
)

max_retries = st.sidebar.slider(
    "Max retries per site", min_value=1, max_value=6,
    value=config.MAX_RETRIES,
    help="How many times to retry a failed request before marking it as failed."
)

retry_delay = st.sidebar.slider(
    "Delay between retries (seconds)", min_value=0, max_value=10,
    value=config.RETRY_DELAY,
    help="Pause between retry attempts."
)

max_workers = st.sidebar.slider(
    "Parallel workers", min_value=1, max_value=20,
    value=config.MAX_WORKERS,
    help="Number of websites processed at the same time. Higher = faster, but more likely to trigger rate limits."
)

# Apply the sidebar values to the shared config module for this run,
# so scraper.py (which reads from config.*) picks them up automatically.
config.REQUEST_TIMEOUT = request_timeout
config.MAX_RETRIES = max_retries
config.RETRY_DELAY = retry_delay
config.MAX_WORKERS = max_workers

st.sidebar.divider()
st.sidebar.caption("Changes here apply only to this session and don't modify config.py.")

# --- Input section ---
col1, col2 = st.columns(2)

with col1:
    pasted_text = st.text_area("Paste URLs (one per line)", height=250)

with col2:
    uploaded_file = st.file_uploader("...or upload a .txt file", type=["txt"])

raw_urls = []

if pasted_text.strip():
    raw_urls.extend(pasted_text.strip().splitlines())

if uploaded_file is not None:
    content = uploaded_file.read().decode("utf-8")
    raw_urls.extend(content.strip().splitlines())

urls = deduplicate_urls(raw_urls)

if raw_urls:
    st.info(f"{len(raw_urls)} URLs provided, {len(urls)} unique after removing duplicates.")

# --- Run section ---
if st.button("Start scraping", disabled=(len(urls) == 0)):
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        future_to_url = {executor.submit(scrape_company, url): url for url in urls}
        completed = 0

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
            except Exception:
                data = {"url": url, "emails": "", "phones": "", "status": "error"}

            results.append(data)
            completed += 1
            progress_bar.progress(completed / len(urls))
            status_text.text(f"Processed {completed}/{len(urls)}: {url}")

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
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
