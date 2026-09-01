"""Fetch, parse, and extract contact info from company websites."""

import ipaddress
import logging
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from . import config


# --- SSRF protection ---
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),       # private Class A
    ipaddress.ip_network("172.16.0.0/12"),    # private Class B
    ipaddress.ip_network("192.168.0.0/16"),   # private Class C
    ipaddress.ip_network("169.254.0.0/16"),   # link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
    ipaddress.ip_network("100.64.0.0/10"),    # carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),     # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),     # documentation (TEST-NET-1)
    ipaddress.ip_network("198.51.100.0/24"),  # documentation (TEST-NET-2)
    ipaddress.ip_network("203.0.113.0/24"),   # documentation (TEST-NET-3)
]


def _is_safe_url(url: str) -> bool:
    """Block private, loopback, and link-local IPs plus non-HTTP schemes."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    # Block localhost by default
    if hostname in ("localhost",):
        return False
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
    except (socket.gaierror, ValueError):
        return False
    for net in _BLOCKED_NETWORKS:
        if ip in net:
            return False
    return True


# --- Rate-limiting / politeness delay ---
_last_request_time: dict[str, float] = {}


def _domain_delay(url: str, delay: float) -> None:
    """Sleep if needed to enforce a minimum gap between requests to the same domain."""
    try:
        domain = urlparse(url).hostname or ""
    except ValueError:
        return
    if not domain:
        return
    now = time.monotonic()
    last = _last_request_time.get(domain, 0.0)
    wait = delay - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_request_time[domain] = time.monotonic()


def reset_rate_limiter() -> None:
    """Clear rate limiter state. Call between independent scrape sessions."""
    _last_request_time.clear()


# --- Page fetching ---
def get_page(
    url: str,
    retries: int | None = None,
    timeout: int | None = None,
    per_domain_delay: float | None = None,
) -> str | None:
    """Fetch a page's HTML with retries and per-domain delay."""
    retries = retries if retries is not None else config.MAX_RETRIES
    timeout = timeout if timeout is not None else config.REQUEST_TIMEOUT
    delay = per_domain_delay if per_domain_delay is not None else config.PER_DOMAIN_DELAY
    headers = {"User-Agent": config.USER_AGENT}

    if not _is_safe_url(url):
        logging.warning(f"{url} - blocked by SSRF protection")
        return None

    for attempt in range(1, retries + 1):
        _domain_delay(url, delay)
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response.text
            logging.warning(f"{url} - status {response.status_code} (attempt {attempt}/{retries})")
        except requests.exceptions.Timeout:
            logging.warning(f"{url} - timeout on attempt {attempt}/{retries}")
        except requests.exceptions.SSLError as e:
            logging.warning(f"{url} - SSL error on attempt {attempt}/{retries}: {e}")
            break  # SSL errors won't resolve with retries
        except requests.exceptions.ConnectionError as e:
            logging.warning(f"{url} - connection error on attempt {attempt}/{retries}: {e}")
        except requests.exceptions.TooManyRedirects:
            logging.warning(f"{url} - too many redirects on attempt {attempt}/{retries}")
            break
        except requests.exceptions.RequestException as e:
            logging.warning(f"{url} - request error on attempt {attempt}/{retries}: {e}")

        if attempt < retries:
            time.sleep(config.RETRY_DELAY)

    return None


# --- Language detection ---
def detect_language(soup: BeautifulSoup) -> str:
    """Guess page language from the <html lang> attribute, character analysis
    (Cyrillic, Persian, CJK), or common-word frequency. Defaults to English."""
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        lang_code = html_tag.get("lang").split("-")[0].lower()
        if lang_code in config.CONTACT_KEYWORDS:
            return lang_code

    text = soup.get_text()

    # Character-based detection
    cyrillic_count = len(re.findall(r'[а-яА-Я]', text))
    persian_count = len(re.findall(r'[\u0600-\u06FF]', text))
    cjk_count = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))

    if cyrillic_count > 50:
        return "ru"
    if persian_count > 50:
        return "fa"
    if cjk_count > 50:
        return "zh"

    # Word-frequency detection for European languages
    words = re.findall(r'\b\w+\b', text.lower())
    if len(words) < 20:
        return "en"
    word_set = set(words)

    best_lang = "en"
    best_score = 0
    for lang, common_words in config.LANG_COMMON_WORDS.items():
        score = len(word_set & set(common_words))
        if score > best_score:
            best_score = score
            best_lang = lang

    # Require at least 4 matches to avoid false positives on short pages
    if best_score >= 4:
        return best_lang
    return "en"


# --- Contact link discovery ---
def find_contact_link(soup: BeautifulSoup, base_url: str, lang: str = "en") -> str | None:
    """Find the best contact-page link using language-specific keywords
    plus English as fallback. Scores by keyword match and DOM position
    (nav/header links preferred over footer links)."""
    keywords = set(config.CONTACT_KEYWORDS.get(lang, []))
    keywords.update(config.CONTACT_KEYWORDS.get("en", []))

    all_links = soup.find_all("a", href=True)

    # Count total links to estimate DOM position
    total = max(len(all_links), 1)

    best_url: str | None = None
    best_score: float = -1.0

    for idx, link in enumerate(all_links):
        href = link["href"].lower()
        text = link.get_text(strip=True).lower()
        score = 0.0

        # Keyword scoring
        for kw in keywords:
            if kw == text:
                score += 10  # exact text match
            elif kw in text:
                score += 5  # substring in text
            if kw == href.rstrip("/").rsplit("/", 1)[-1]:
                score += 8  # exact slug match
            elif kw in href:
                score += 3  # substring in href

        if score <= 0:
            continue

        # Prefer links that appear earlier in the DOM (nav/header typically first)
        position_bonus = max(0, 1.0 - (idx / total))
        score += position_bonus * 2

        # Bonus for nav-like containers
        parent = link.parent
        for _ in range(5):
            if parent is None:
                break
            parent_attrs = parent.get("class", [])
            parent_name = parent.name.lower() if parent.name else ""
            attr_str = " ".join(str(a) for a in parent_attrs).lower()
            if any(k in parent_name or k in attr_str
                   for k in ("nav", "menu", "header", "top-bar", "toolbar")):
                score += 3
                break
            parent = parent.parent if hasattr(parent, "parent") else None

        if score > best_score:
            best_score = score
            best_url = urljoin(base_url, link["href"])

    return best_url


# --- Email extraction ---
def extract_emails(text: str) -> list[str]:
    """Extract emails from text, rejecting common false positives
    (e.g. image filenames like logo@2x.png) and deduplicating case-insensitively."""
    raw = re.findall(config.EMAIL_PATTERN, text)
    seen: dict[str, str] = {}
    for email in raw:
        lower = email.lower()
        if lower not in seen:
            seen[lower] = email
    return list(seen.values())


# --- Phone extraction ---
def _phone_near_context(text: str, match_start: int, match_end: int) -> bool:
    """Check if a phone-indicating keyword appears within 60 chars of the match."""
    window = 60
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)
    surrounding = text[start:end].lower()
    for kw in config.PHONE_CONTEXT_KEYWORDS:
        if kw in surrounding:
            return True
    return False


def extract_phones(text: str) -> list[str]:
    """Extract phone numbers from text. Requires nearby keywords to reduce
    false positives, then deduplicates overlapping matches."""
    # Collect candidates with positions
    candidates: list[tuple[str, int, int]] = []
    for pattern in config.PHONE_PATTERNS:
        for m in re.finditer(pattern, text):
            candidates.append((m.group(), m.start(), m.end()))

    # Filter by digit count and nearby keywords
    parsed: list[tuple[str, str, int, int]] = []
    for candidate, start, end in candidates:
        digits_only = re.sub(r'\D', '', candidate)
        if config.MIN_PHONE_DIGITS <= len(digits_only) <= config.MAX_PHONE_DIGITS:
            if _phone_near_context(text, start, end):
                parsed.append((candidate.strip(), digits_only, start, end))

    # Remove candidates that are substrings of others and overlap in position
    filtered: list[tuple[str, str, int, int]] = []
    for cleaned, digits, start, end in parsed:
        is_partial = False
        for other_cleaned, other_digits, other_start, other_end in parsed:
            if (digits != other_digits
                    and digits in other_digits
                    and abs(start - other_start) < len(other_digits)):
                is_partial = True
                break
        if not is_partial:
            filtered.append((cleaned, digits, start, end))

    # Keep unique numbers, preserve order
    valid_phones: list[str] = []
    seen_digits: set[str] = set()
    for cleaned, digits, _start, _end in filtered:
        if digits not in seen_digits:
            seen_digits.add(digits)
            valid_phones.append(cleaned)

    return valid_phones


# --- Table-based person extraction ---
def extract_people_from_tables(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Extract per-person contact rows (name, phone, email, role) from HTML
    tables. Useful for staff directory pages."""
    people: list[dict[str, str]] = []
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


# --- URL deduplication ---
def deduplicate_urls(urls: list[str]) -> list[str]:
    """Remove duplicate URLs, preserving original order.
    Normalizes protocol, case, trailing slashes, and www prefix."""
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        cleaned = url.strip()
        if not cleaned:
            continue
        normalized = cleaned.lower().rstrip("/")
        normalized = normalized.replace("https://", "").replace("http://", "")
        # Strip leading www. for comparison
        if normalized.startswith("www."):
            normalized = normalized[4:]
        if normalized not in seen:
            seen.add(normalized)
            result.append(cleaned)
    return result


# --- Main pipeline ---
def scrape_company(url: str, **kwargs: Any) -> dict[str, Any]:
    """Full pipeline for a single URL: fetch, detect language, extract
    contacts from homepage, fall back to contact page if nothing found."""
    timeout = kwargs.get("timeout")
    max_retries = kwargs.get("max_retries")
    per_domain_delay = kwargs.get("per_domain_delay")

    html = get_page(url, retries=max_retries, timeout=timeout,
                    per_domain_delay=per_domain_delay)
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
            contact_html = get_page(contact_url, retries=max_retries,
                                    timeout=timeout,
                                    per_domain_delay=per_domain_delay)
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


def run_scrape(
    urls: list[str],
    max_workers: int | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
    per_domain_delay: float | None = None,
    progress_callback: Any | None = None,
) -> list[dict[str, Any]]:
    """Run scrape_company on all URLs in parallel, preserving input order."""
    workers = max_workers or config.MAX_WORKERS
    results: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_url = {
            executor.submit(
                scrape_company, url,
                timeout=timeout, max_retries=max_retries,
                per_domain_delay=per_domain_delay,
            ): url
            for url in urls
        }

        completed = 0
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
            except Exception as e:
                data = {"url": url, "emails": "", "phones": "", "status": "error"}
                logging.error(f"{url} - unexpected error: {e}")

            if data["status"] != "ok":
                logging.warning(f"{url} - {data['status']}")

            results[url] = data
            completed += 1
            if progress_callback:
                progress_callback(completed, len(urls))

    # Return results in the same order as the input URLs (fix #12)
    return [results[url] for url in urls if url in results]
