import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
from tqdm import tqdm

import config
from scraper import scrape_company, deduplicate_urls

logging.basicConfig(
    filename=config.ERROR_LOG_FILE,
    level=logging.WARNING,
    format="%(asctime)s - %(message)s"
)


def load_urls(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    return urls


def save_to_excel(results, filepath):
    df = pd.DataFrame(results)

    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Companies")
        worksheet = writer.sheets["Companies"]

        for col_num, column_title in enumerate(df.columns, 1):
            col_letter = get_column_letter(col_num)

            header_cell = worksheet[f"{col_letter}1"]
            header_cell.font = Font(bold=True)
            header_cell.alignment = Alignment(horizontal="center")

            max_length = max(
                df[column_title].astype(str).map(len).max(),
                len(column_title)
            )
            worksheet.column_dimensions[col_letter].width = min(max_length + 5, 50)

        worksheet.freeze_panes = "A2"


def run_scrape(urls):
    """Runs scrape_company on all URLs in parallel, with a progress bar."""
    results = []
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        future_to_url = {executor.submit(scrape_company, url): url for url in urls}

        for future in tqdm(as_completed(future_to_url), total=len(urls), desc="Scraping"):
            url = future_to_url[future]
            try:
                data = future.result()
            except Exception as e:
                data = {"url": url, "emails": "", "phones": "", "status": "error"}
                logging.error(f"{url} - unexpected error: {e}")

            if data["status"] != "ok":
                logging.warning(f"{url} - {data['status']}")

            results.append(data)

    return results


def main():
    raw_urls = load_urls("input.txt")
    urls = deduplicate_urls(raw_urls)

    print(f"Loaded {len(raw_urls)} URLs, {len(urls)} unique after deduplication")

    results = run_scrape(urls)

    save_to_excel(results, config.OUTPUT_EXCEL)
    print(f"Done. Saved to {config.OUTPUT_EXCEL}")
    print(f"Check {config.ERROR_LOG_FILE} for any failed or empty results.")


if __name__ == "__main__":
    main()
