"""Tests for the company_scraper package."""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock

import pytest

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from company_scraper import config
from company_scraper.scraper import (
    extract_emails,
    extract_phones,
    deduplicate_urls,
    detect_language,
    find_contact_link,
    get_page,
    scrape_company,
    _is_safe_url,
    _phone_near_context,
    reset_rate_limiter,
)
from company_scraper.main import load_urls, save_to_excel

from bs4 import BeautifulSoup


# =========================================================================
# extract_emails
# =========================================================================
class TestExtractEmails:
    def test_finds_valid_email(self):
        text = "Contact us at info@example.com for more details."
        assert extract_emails(text) == ["info@example.com"]

    def test_finds_multiple_emails(self):
        text = "Sales: sales@example.com Support: support@example.com"
        result = extract_emails(text)
        assert "sales@example.com" in result
        assert "support@example.com" in result
        assert len(result) == 2

    def test_returns_empty_when_none_found(self):
        text = "There is no email address in this sentence."
        assert extract_emails(text) == []

    def test_deduplicates_case_insensitively(self):
        text = "Contact: Info@Example.com or info@example.com for support."
        result = extract_emails(text)
        assert len(result) == 1
        assert result[0].lower() == "info@example.com"

    def test_rejects_image_filename_false_positive_png(self):
        text = "Download the logo@2x.png background image"
        assert extract_emails(text) == []

    def test_rejects_image_filename_false_positive_webp(self):
        text = "Use avatar@3x.webp for retina displays"
        assert extract_emails(text) == []

    def test_rejects_image_filename_false_positive_jpg(self):
        text = "See banner@2x.jpg for high-res version"
        assert extract_emails(text) == []

    def test_rejects_image_filename_false_positive_svg(self):
        text = "Icon is icon@2x.svg in the assets folder"
        assert extract_emails(text) == []

    def test_rejects_image_filename_false_positive_gif(self):
        text = "Animation loading@2x.gif please wait"
        assert extract_emails(text) == []

    def test_accepts_valid_email_with_subdomain(self):
        text = "Reach us at mail.server@example.co.uk"
        result = extract_emails(text)
        assert "mail.server@example.co.uk" in result

    def test_accepts_valid_email_with_plus(self):
        text = "Email user+tag@gmail.com for info"
        result = extract_emails(text)
        assert "user+tag@gmail.com" in result

    def test_rejects_exe_extension(self):
        text = "Download setup@2x.exe installer"
        assert extract_emails(text) == []

    def test_rejects_docx_extension(self):
        text = "File report@final.docx attached"
        assert extract_emails(text) == []

    def test_rejects_csv_extension(self):
        text = "Export data@export.csv for analysis"
        assert extract_emails(text) == []


# =========================================================================
# extract_phones
# =========================================================================
class TestExtractPhones:
    def test_finds_international_format(self):
        text = "Call us: +7 495 123 45 67"
        result = extract_phones(text)
        assert len(result) == 1

    def test_ignores_copyright_years(self):
        text = "© 2012-2026 Example Company. All rights reserved."
        result = extract_phones(text)
        assert result == []

    def test_finds_russian_domestic_format(self):
        text = "Телефон/факс 8 (4922) 53-38-36"
        result = extract_phones(text)
        assert len(result) == 1

    def test_returns_empty_when_none_found(self):
        text = "No phone number is mentioned here at all."
        assert extract_phones(text) == []

    def test_rejects_order_number(self):
        text = "Order #1234567890 placed on 2024-01-15"
        result = extract_phones(text)
        assert result == []

    def test_rejects_barcode_sku(self):
        text = "Product SKU: 4901234567894"
        result = extract_phones(text)
        assert result == []

    def test_finds_phone_with_context_keyword(self):
        text = "Phone: 5551234567 for information"
        result = extract_phones(text)
        assert len(result) == 1

    def test_does_not_drop_independent_numbers(self):
        text = "Head office tel +1 234-567-8900 also reachable at fax 234-567-8900"
        result = extract_phones(text)
        # Both numbers have nearby keywords and should be returned
        assert len(result) == 2

    def test_finds_phone_with_tel_keyword(self):
        text = "Tel: (495) 123-45-67 for sales"
        result = extract_phones(text)
        assert len(result) == 1

    def test_finds_phone_with_call_keyword(self):
        text = "Call +1-800-555-0199 for support"
        result = extract_phones(text)
        assert len(result) == 1

    def test_finds_phone_with_fax_keyword(self):
        text = "Fax: +44 20 7946 0958 for documents"
        result = extract_phones(text)
        assert len(result) == 1

    def test_finds_phone_with_mobile_keyword(self):
        text = "Mobile: +91 98765 43210"
        result = extract_phones(text)
        assert len(result) == 1

    def test_rejects_zip_code_without_context(self):
        text = "Zip code 90210-1234 is in Beverly Hills"
        result = extract_phones(text)
        assert result == []

    def test_finds_german_phone_with_kontakt(self):
        text = "Kontakt: +49 30 12345678"
        result = extract_phones(text)
        assert len(result) == 1

    def test_finds_french_phone_with_telephone(self):
        text = "Téléphone: +33 1 23 45 67 89"
        result = extract_phones(text)
        assert len(result) == 1

    def test_finds_chinese_phone_with_dianhua(self):
        text = "电话: +86 10 12345678"
        result = extract_phones(text)
        assert len(result) == 1


# =========================================================================
# deduplicate_urls
# =========================================================================
class TestDeduplicateUrls:
    def test_removes_exact_duplicates(self):
        urls = ["https://example.com", "https://example.com"]
        assert deduplicate_urls(urls) == ["https://example.com"]

    def test_ignores_protocol_and_case(self):
        urls = ["https://Example.com", "http://example.com"]
        result = deduplicate_urls(urls)
        assert len(result) == 1

    def test_ignores_trailing_slash(self):
        urls = ["https://example.com/", "https://example.com"]
        result = deduplicate_urls(urls)
        assert len(result) == 1

    def test_keeps_distinct_urls(self):
        urls = ["https://example.com", "https://another.com"]
        result = deduplicate_urls(urls)
        assert len(result) == 2

    def test_ignores_blank_lines(self):
        urls = ["https://example.com", "", "   "]
        result = deduplicate_urls(urls)
        assert result == ["https://example.com"]

    def test_normalizes_www_vs_nonwww(self):
        urls = ["https://www.example.com", "https://example.com"]
        result = deduplicate_urls(urls)
        assert len(result) == 1

    def test_preserves_original_url形式(self):
        urls = ["https://www.Example.com", "https://example.com"]
        result = deduplicate_urls(urls)
        assert result[0] == "https://www.Example.com"

    def test_normalizes_www_with_trailing_slash(self):
        urls = ["https://www.example.com/", "https://example.com"]
        result = deduplicate_urls(urls)
        assert len(result) == 1


# =========================================================================
# detect_language
# =========================================================================
class TestDetectLanguage:
    def _make_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def test_lang_attribute_english(self):
        soup = self._make_soup('<html lang="en"><body>Hello</body></html>')
        assert detect_language(soup) == "en"

    def test_lang_attribute_russian(self):
        soup = self._make_soup('<html lang="ru"><body>Привет</body></html>')
        assert detect_language(soup) == "ru"

    def test_lang_attribute_with_region(self):
        soup = self._make_soup('<html lang="de-DE"><body>Hallo</body></html>')
        assert detect_language(soup) == "de"

    def test_cyrillic_detection(self):
        text = " " + "Привет мир это тестовый текст для определения языка " * 5
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "ru"

    def test_persian_detection(self):
        text = " " + "این یک متن فارسی است برای تست تشخیص زبان " * 5
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "fa"

    def test_chinese_detection(self):
        text = " " + "这是一个中文文本用于测试语言检测功能的准确性 " * 5
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "zh"

    def test_german_word_frequency(self):
        text = "Die der und ist ein eine für auf mit nicht sind haben wir kann " \
               "aber oder bei nach wie auch als so um am im den dem des sich " \
               "uns ihr ihm sie wenn noch da du ich es von zu in by the and for"
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "de"

    def test_french_word_frequency(self):
        text = "Les des une est dans pour pas qui sur avec tout mais plus cette " \
               "sont fait nous vous leur aussi bien très peut deux fois mon son " \
               "ses nos vos par du au aux je ne se ya un en que elle ils"
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "fr"

    def test_spanish_word_frequency(self):
        text = "Los las una está por que con para más del como pero sus este esta " \
               "fue han hay desde todo nos entre también sobre puede cada otro " \
               "otra muy ser son están estos estas su al el en es lo se un ya le no"
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "es"

    def test_defaults_to_english_when_unknown(self):
        text = "Some random text without enough signal"
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "en"

    def test_german_without_lang_attribute(self):
        # Enough German common words to trigger detection
        text = "Kontaktieren Sie uns bitte. Wir sind für Sie da. " \
               "Rufen Sie uns an oder schreiben Sie eine E-Mail. " \
               "Die der und ist ein eine für auf mit nicht sind haben wir " \
               "kann aber oder bei nach wie auch als so um"
        soup = self._make_soup(f"<html><body>{text}</body></html>")
        assert detect_language(soup) == "de"


# =========================================================================
# find_contact_link
# =========================================================================
class TestFindContactLink:
    def _make_soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def test_finds_contact_link_by_text(self):
        html = """
        <html><body>
            <a href="/about">About</a>
            <a href="/contact">Contact Us</a>
            <a href="/blog">Blog</a>
        </body></html>
        """
        soup = self._make_soup(html)
        result = find_contact_link(soup, "https://example.com")
        assert result is not None
        assert "contact" in result

    def test_finds_contact_link_by_href(self):
        html = """
        <html><body>
            <a href="/about-us">About</a>
            <a href="/contact-us">Get in touch</a>
        </body></html>
        """
        soup = self._make_soup(html)
        result = find_contact_link(soup, "https://example.com")
        assert result is not None
        assert "contact" in result

    def test_returns_none_when_no_contact_link(self):
        html = """
        <html><body>
            <a href="/about">About</a>
            <a href="/blog">Blog</a>
        </body></html>
        """
        soup = self._make_soup(html)
        result = find_contact_link(soup, "https://example.com")
        assert result is None

    def test_prioritizes_exact_text_match(self):
        html = """
        <html><body>
            <a href="/about-company">About Our Company</a>
            <a href="/contact">Contact</a>
        </body></html>
        """
        soup = self._make_soup(html)
        result = find_contact_link(soup, "https://example.com")
        assert result is not None
        assert "contact" in result

    def test_uses_language_keywords(self):
        html = """
        <html><body>
            <a href="/uber-uns">Über uns</a>
            <a href="/kontakt">Kontakt</a>
        </body></html>
        """
        soup = self._make_soup(html)
        result = find_contact_link(soup, "https://example.com", lang="de")
        assert result is not None
        assert "kontakt" in result

    def test_prefers_nav_links(self):
        html = """
        <html><body>
            <nav>
                <a href="/home">Home</a>
                <a href="/contact-nav">Contact</a>
            </nav>
            <footer>
                <a href="/contact-footer">Contact Us</a>
            </footer>
        </body></html>
        """
        soup = self._make_soup(html)
        result = find_contact_link(soup, "https://example.com")
        assert result is not None
        # The nav link should be preferred (earlier in DOM + nav container bonus)
        assert "contact-nav" in result


# =========================================================================
# _is_safe_url (SSRF protection)
# =========================================================================
class TestIsSafeUrl:
    def test_allows_public_http(self):
        assert _is_safe_url("http://example.com") is True

    def test_allows_public_https(self):
        assert _is_safe_url("https://example.com") is True

    def test_blocks_ftp(self):
        assert _is_safe_url("ftp://example.com") is False

    def test_blocks_file_scheme(self):
        assert _is_safe_url("file:///etc/passwd") is False

    def test_blocks_localhost(self):
        assert _is_safe_url("http://localhost") is False

    def test_blocks_localhost_with_port(self):
        assert _is_safe_url("http://localhost:8080") is False

    def test_blocks_loopback_ip(self):
        assert _is_safe_url("http://127.0.0.1") is False

    def test_blocks_private_10_x(self):
        assert _is_safe_url("http://10.0.0.1") is False

    def test_blocks_private_172_16(self):
        assert _is_safe_url("http://172.16.0.1") is False

    def test_blocks_private_192_168(self):
        assert _is_safe_url("http://192.168.1.1") is False

    def test_blocks_link_local(self):
        assert _is_safe_url("http://169.254.169.254") is False

    def test_blocks_cloud_metadata(self):
        assert _is_safe_url("http://169.254.169.254/latest/meta-data/") is False

    def test_blocks_ipv6_loopback(self):
        assert _is_safe_url("http://[::1]") is False

    def test_blocks_invalid_url(self):
        assert _is_safe_url("not a url") is False


# =========================================================================
# get_page
# =========================================================================
class TestGetPage:
    @patch("company_scraper.scraper.requests.get")
    @patch("company_scraper.scraper._is_safe_url", return_value=True)
    @patch("company_scraper.scraper._domain_delay")
    def test_returns_html_on_success(self, mock_delay, mock_safe, mock_get):
        mock_get.return_value = Mock(status_code=200, text="<html>OK</html>")
        result = get_page("https://example.com", per_domain_delay=0)
        assert result == "<html>OK</html>"

    @patch("company_scraper.scraper._is_safe_url", return_value=False)
    def test_blocks_unsafe_url(self, mock_safe):
        result = get_page("http://127.0.0.1")
        assert result is None

    @patch("company_scraper.scraper.requests.get")
    @patch("company_scraper.scraper._is_safe_url", return_value=True)
    @patch("company_scraper.scraper._domain_delay")
    def test_returns_none_on_404(self, mock_delay, mock_safe, mock_get):
        mock_get.return_value = Mock(status_code=404)
        result = get_page("https://example.com", retries=1, per_domain_delay=0)
        assert result is None

    @patch("company_scraper.scraper.requests.get")
    @patch("company_scraper.scraper._is_safe_url", return_value=True)
    @patch("company_scraper.scraper._domain_delay")
    def test_retries_on_timeout(self, mock_delay, mock_safe, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("timeout")
        result = get_page("https://example.com", retries=2, per_domain_delay=0)
        assert result is None
        assert mock_get.call_count == 2

    @patch("company_scraper.scraper.requests.get")
    @patch("company_scraper.scraper._is_safe_url", return_value=True)
    @patch("company_scraper.scraper._domain_delay")
    def test_does_not_retry_on_ssl_error(self, mock_delay, mock_safe, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.SSLError("ssl error")
        result = get_page("https://example.com", retries=3, per_domain_delay=0)
        assert result is None
        # SSL errors should not be retried
        assert mock_get.call_count == 1


# =========================================================================
# scrape_company (end-to-end pipeline with mocked HTTP)
# =========================================================================
class TestScrapeCompany:
    @patch("company_scraper.scraper.get_page")
    def test_returns_failed_when_page_not_loaded(self, mock_get):
        mock_get.return_value = None
        result = scrape_company("https://example.com")
        assert result["status"] == "failed_to_load"
        assert result["url"] == "https://example.com"

    @patch("company_scraper.scraper.get_page")
    def test_extracts_email_from_homepage(self, mock_get):
        mock_get.return_value = """
        <html lang="en">
        <body>
            <p>Email us at info@example.com for more information.</p>
            <p>Phone: +1 555 123 4567</p>
        </body>
        </html>
        """
        result = scrape_company("https://example.com")
        assert result["status"] == "ok"
        assert "info@example.com" in result["emails"]
        assert "+1 555 123 4567" in result["phones"]

    @patch("company_scraper.scraper.get_page")
    def test_falls_back_to_contact_page(self, mock_get):
        homepage = """
        <html lang="en">
        <body>
            <p>Welcome to our company</p>
            <a href="/contact">Contact Us</a>
        </body>
        </html>
        """
        contact_page = """
        <html lang="en">
        <body>
            <p>Email: sales@example.com</p>
            <p>Tel: +44 20 7946 0958</p>
        </body>
        </html>
        """
        mock_get.side_effect = [homepage, contact_page]
        result = scrape_company("https://example.com")
        assert result["status"] == "ok"
        assert "sales@example.com" in result["emails"]

    @patch("company_scraper.scraper.get_page")
    def test_returns_no_contact_found_when_empty(self, mock_get):
        mock_get.return_value = """
        <html lang="en">
        <body><p>Welcome to our homepage.</p></body>
        </html>
        """
        result = scrape_company("https://example.com")
        assert result["status"] == "no_contact_found"

    @patch("company_scraper.scraper.get_page")
    def test_passes_settings_to_get_page(self, mock_get):
        mock_get.return_value = """
        <html lang="en"><body><p>No contact info here.</p></body></html>
        """
        scrape_company(
            "https://example.com",
            timeout=5,
            max_retries=2,
            per_domain_delay=0.5,
        )
        # get_page should have been called with the overrides
        assert mock_get.call_count >= 1
        call_kwargs = mock_get.call_args
        # Check that timeout was passed through
        assert call_kwargs[1].get("timeout") == 5 or call_kwargs[0][1] == 2


# =========================================================================
# main.py helpers
# =========================================================================
class TestLoadUrls:
    def test_loads_urls_from_file(self, tmp_path):
        input_file = tmp_path / "urls.txt"
        input_file.write_text("https://a.com\nhttps://b.com\n\nhttps://c.com\n")
        result = load_urls(str(input_file))
        assert result == ["https://a.com", "https://b.com", "https://c.com"]

    def test_skips_blank_lines(self, tmp_path):
        input_file = tmp_path / "urls.txt"
        input_file.write_text("https://a.com\n   \n\nhttps://b.com\n")
        result = load_urls(str(input_file))
        assert len(result) == 2


class TestSaveToExcel:
    def test_creates_excel_file(self, tmp_path):
        output_file = tmp_path / "test_output.xlsx"
        results = [
            {"url": "https://a.com", "emails": "a@a.com", "phones": "+1 555 123 4567", "status": "ok"},
            {"url": "https://b.com", "emails": "", "phones": "", "status": "no_contact_found"},
        ]
        save_to_excel(results, str(output_file))
        assert output_file.exists()
        assert output_file.stat().st_size > 0


# =========================================================================
# _phone_near_context
# =========================================================================
class TestPhoneNearContext:
    def test_returns_true_with_phone_keyword_before(self):
        assert _phone_near_context("Call 5551234567 now", 5, 15) is True

    def test_returns_true_with_phone_keyword_after(self):
        assert _phone_near_context("Number 5551234567 phone", 7, 17) is True

    def test_returns_true_with_tel_keyword(self):
        assert _phone_near_context("Tel: 5551234567", 5, 15) is True

    def test_returns_false_without_keyword(self):
        assert _phone_near_context("Order #5551234567 placed", 8, 18) is False

    def test_returns_true_with_fax_keyword(self):
        assert _phone_near_context("Fax +1 555 123 4567", 0, 14) is True

    def test_returns_true_within_window(self):
        # Keyword is 59 chars before the match (within 60-char window)
        prefix = "A" * 55 + " phone "
        text = prefix + "5551234567"
        start = len(prefix)
        assert _phone_near_context(text, start, start + 10) is True

    def test_returns_false_outside_window(self):
        # Keyword is >60 chars before the match (outside 60-char window)
        prefix = "A" * 70 + " phone " + "A" * 70
        text = prefix + "5551234567"
        start = len(prefix)
        assert _phone_near_context(text, start, start + 10) is False


# =========================================================================
# reset_rate_limiter
# =========================================================================
class TestRateLimiter:
    def test_reset_clears_state(self):
        from company_scraper.scraper import _last_request_time
        _last_request_time["example.com"] = 123.0
        reset_rate_limiter()
        assert "example.com" not in _last_request_time
