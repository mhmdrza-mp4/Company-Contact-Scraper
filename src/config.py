# -----------------------------
# Network / request settings
# -----------------------------
REQUEST_TIMEOUT = 10          # seconds to wait for a response before giving up
MAX_RETRIES = 3                # how many times to retry a failed request
RETRY_DELAY = 2                # seconds to wait between retries

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# -----------------------------
# Concurrency settings
# -----------------------------
MAX_WORKERS = 8                 # number of websites processed in parallel

# -----------------------------
# Output settings
# -----------------------------
OUTPUT_EXCEL = "companies_output.xlsx"
ERROR_LOG_FILE = "errors.log"

# -----------------------------
# Contact page keywords per detected language
# Used to find the "Contact Us" link on a homepage
# -----------------------------
CONTACT_KEYWORDS = {
    "en": ["contact", "contact-us", "get-in-touch", "about"],
    "ru": ["контакт", "контакты", "связаться", "свяжитесь"],
    "fa": ["تماس", "ارتباط با ما"],
    "de": ["kontakt", "impressum"],
    "fr": ["contact", "contactez-nous"],
    "es": ["contacto", "contactenos"],
    "zh": ["联系", "联系我们"],
}

# -----------------------------
# Email pattern (kept simple and general-purpose)
# -----------------------------
EMAIL_PATTERN = r'[\w\.-]+@[\w\.-]+\.\w+'

# -----------------------------
# Phone patterns per region
# Each entry is tried in order; more specific patterns first
# -----------------------------
PHONE_PATTERNS = [
    r'\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\d\s\-]{6,}\d',   # international format, e.g. +7 (495) 123-45-67
    r'\(?\d{2,4}\)?[\s\-]?\d{2,3}[\s\-]?\d{2,3}[\s\-]?\d{2,4}',  # local format, e.g. (495) 123-45-67
    r'8\s?\(?\d{3,4}\)?[\d\s\-]{6,}\d',                # Russian domestic format starting with 8
]

MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 13
