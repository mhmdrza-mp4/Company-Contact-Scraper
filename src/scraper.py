import re
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import config


def get_page(url, retries=None):
    """Fetch a page's HTML with automatic retries on failure."""
    retries = retries if retries is not None else config.MAX_RETRIES
    headers = {"User-Agent": config.USER_AGENT}

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
            if response.status_code == 200:
                return response.text
            else:
                logging.warning(f"{url} - status {response.status_code} (attempt {attempt}/{retries})")
        except requests.exceptions.RequestException as e:
            logging.warning(f"{url} - request error on attempt {attempt}/{retries}: {e}")

        if attempt < retries:
            time.sleep(config.RETRY_DELAY)

    return None


def detect_language(soup):
    """Guess the page language: first from the <html lang="..."> attribute,
    then by counting Cyrillic / Persian characters, defaulting to English."""
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        lang_code = html_tag.get("lang").split("-")[0].lower()
        if lang_code in config.CONTACT_KEYWORDS:
            return lang_code

    text = soup.get_text()
    cyrillic_count = len(re.findall(r'[а-яА-Я]', text))
    persian_count = len(re.findall(r'[\u0600-\u06FF]', text))

    if cyrillic_count > 50:
        return "ru"
    if persian_count > 50:
        return "fa"
    return "en"


def find_contact_link(soup, base_url, lang="en"):
    """Look for a link to the contact page, using language-specific keywords
    plus English as a fallback (many non-English sites still use English URLs)."""
    keywords = set(config.CONTACT_KEYWORDS.get(lang, []))
    keywords.update(config.CONTACT_KEYWORDS.get("en", []))

    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        text = link.get_text().lower()
        if any(kw in href or kw in text for kw in keywords):
            return urljoin(base_url, link["href"])
    return None


def extract_emails(text):
    return list(set(re.findall(config.EMAIL_PATTERN, text)))


def extract_phones(text):
    candidates = []
    for pattern in config.PHONE_PATTERNS:
        candidates.extend(re.findall(pattern, text))

    parsed = []
    for candidate in candidates:
        digits_only = re.sub(r'\D', '', candidate)
        if config.MIN_PHONE_DIGITS <= len(digits_only) <= config.MAX_PHONE_DIGITS:
            parsed.append((candidate.strip(), digits_only))

    # Different patterns can match overlapping substrings of the same phone
    # number (e.g. the full number and a shorter piece of it). Keep only the
    # longest version when one match's digits are fully contained in another's.
    filtered = []
    for cleaned, digits in parsed:
        is_partial = any(
            digits != other_digits and digits in other_digits
            for _, other_digits in parsed
        )
        if not is_partial:
            filtered.append(cleaned)

    valid_phones = []
    for cleaned in filtered:
        if cleaned not in valid_phones:
            valid_phones.append(cleaned)

    return valid_phones


def extract_people_from_tables(soup):
    """Extract per-person contact rows from HTML tables (name, phone, email, role).
    Useful for 'VIP' / level-3 style data where individual staff are listed."""
    people = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            row_text = " | ".join(c.get_text(strip=True) for c in cells)

            emails = extract_emails(row_text)
            phones = extract_phones(row_text)

            if emails or phones:
                people.append({
                    "name": cells[0].get_text(strip=True),
                    "emails": ", ".join(emails),
                    "phones": ", ".join(phones),
                })
    return people


def scrape_company(url):
    """Full pipeline for a single company: fetch, detect language,
    extract contact info from homepage, fall back to contact page if needed."""
    html = get_page(url)
    if not html:
        return {"url": url, "emails": "", "phones": "", "status": "failed_to_load"}

    soup = BeautifulSoup(html, "html.parser")
    lang = detect_language(soup)

    page_text = soup.get_text(separator=" ")
    emails = extract_emails(page_text)
    phones = extract_phones(page_text)

    if not emails and not phones:
        contact_url = find_contact_link(soup, url, lang=lang)
        if contact_url:
            contact_html = get_page(contact_url)
            if contact_html:
                contact_soup = BeautifulSoup(contact_html, "html.parser")
                contact_text = contact_soup.get_text(separator=" ")
                emails = extract_emails(contact_text)
                phones = extract_phones(contact_text)

    return {
        "url": url,
        "emails": ", ".join(emails) if emails else "",
        "phones": ", ".join(phones) if phones else "",
        "status": "ok" if (emails or phones) else "no_contact_found",
    }


def deduplicate_urls(urls):
    """Remove duplicate URLs while preserving the original order.
    Two URLs are considered the same if they match ignoring case,
    trailing slashes, and http/https differences."""
    seen = set()
    result = []
    for url in urls:
        cleaned = url.strip()
        if not cleaned:
            continue
        normalized = cleaned.lower().rstrip("/")
        normalized = normalized.replace("https://", "").replace("http://", "")
        if normalized not in seen:
            seen.add(normalized)
            result.append(cleaned)
    return result
