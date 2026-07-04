import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scraper import extract_emails, extract_phones, deduplicate_urls


# --- extract_emails ---

def test_extract_emails_finds_valid_email():
    text = "Contact us at info@example.com for more details."
    assert extract_emails(text) == ["info@example.com"]


def test_extract_emails_finds_multiple_emails():
    text = "Sales: sales@example.com Support: support@example.com"
    result = extract_emails(text)
    assert "sales@example.com" in result
    assert "support@example.com" in result
    assert len(result) == 2


def test_extract_emails_returns_empty_when_none_found():
    text = "There is no email address in this sentence."
    assert extract_emails(text) == []


def test_extract_emails_removes_duplicates():
    text = "info@example.com and again info@example.com"
    assert extract_emails(text) == ["info@example.com"]


# --- extract_phones ---

def test_extract_phones_finds_international_format():
    text = "Call us: +7 495 123 45 67"
    result = extract_phones(text)
    assert len(result) == 1


def test_extract_phones_ignores_copyright_years():
    text = "© 2012-2026 Example Company. All rights reserved."
    result = extract_phones(text)
    assert result == []


def test_extract_phones_finds_russian_domestic_format():
    text = "Телефон/факс 8 (4922) 53-38-36"
    result = extract_phones(text)
    assert len(result) == 1


def test_extract_phones_returns_empty_when_none_found():
    text = "No phone number is mentioned here at all."
    assert extract_phones(text) == []


# --- deduplicate_urls ---

def test_deduplicate_urls_removes_exact_duplicates():
    urls = ["https://example.com", "https://example.com"]
    assert deduplicate_urls(urls) == ["https://example.com"]


def test_deduplicate_urls_ignores_protocol_and_case_differences():
    urls = ["https://Example.com", "http://example.com"]
    result = deduplicate_urls(urls)
    assert len(result) == 1


def test_deduplicate_urls_ignores_trailing_slash():
    urls = ["https://example.com/", "https://example.com"]
    result = deduplicate_urls(urls)
    assert len(result) == 1


def test_deduplicate_urls_keeps_distinct_urls():
    urls = ["https://example.com", "https://another.com"]
    result = deduplicate_urls(urls)
    assert len(result) == 2


def test_deduplicate_urls_ignores_blank_lines():
    urls = ["https://example.com", "", "   "]
    result = deduplicate_urls(urls)
    assert result == ["https://example.com"]
