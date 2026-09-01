# --- Request settings ---
REQUEST_TIMEOUT: int = 10
MAX_RETRIES: int = 3
RETRY_DELAY: int = 2
PER_DOMAIN_DELAY: float = 1.0

USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# --- Concurrency ---
MAX_WORKERS: int = 8

# --- Output ---
OUTPUT_EXCEL: str = "companies_output.xlsx"
ERROR_LOG_FILE: str = "errors.log"

# Contact page keywords per language
CONTACT_KEYWORDS: dict[str, list[str]] = {
    "en": ["contact", "contact-us", "get-in-touch"],
    "ru": ["контакт", "контакты", "связаться", "свяжитесь"],
    "fa": ["تماس", "ارتباط با ما"],
    "de": ["kontakt", "impressum"],
    "fr": ["contact", "contactez-nous"],
    "es": ["contacto", "contactenos"],
    "zh": ["联系", "联系我们"],
}

# Common words for language detection
LANG_COMMON_WORDS: dict[str, list[str]] = {
    "de": ["die", "der", "und", "ist", "ein", "eine", "für", "auf", "mit", "nicht",
           "sind", "haben", "wir", "kann", "aber", "oder", "bei", "nach", "wie",
           "auch", "als", "so", "um", "am", "im", "den", "dem", "des", "sich",
           "uns", "ihr", "ihm", "sie", "wenn", "noch", "da", "du", "ich", "es",
           "von", "im", "an", "da", "zu", "in", "by", "the", "and", "for"],
    "fr": ["les", "des", "une", "est", "dans", "pour", "pas", "qui", "sur", "avec",
           "tout", "mais", "plus", "cette", "sont", "fait", "nous", "vous", "leur",
           "aussi", "bien", "très", "peut", "deux", "fois", "mon", "son", "mes",
           "ses", "nos", "vos", "par", "du", "au", "aux", "je", "ne", "se", "ya",
           "un", "en", "que", "qui", "est", "elle", "nous", "vous", "ils"],
    "es": ["los", "las", "una", "está", "por", "que", "con", "para", "más", "del",
           "como", "pero", "sus", "este", "esta", "fue", "han", "hay", "desde",
           "todo", "nos", "entre", "tiene", "también", "sobre", "puede", "cada",
           "otro", "otra", "muy", "ser", "son", "están", "estas", "estos",
           "su", "al", "el", "en", "es", "lo", "se", "un", "ya", "le", "no"],
}

# Email regex — rejects image/file extensions as TLD to avoid false positives
EMAIL_PATTERN: str = (
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.(?!png|jpe?g|gif|webp|svg|ico'
    r'|bmp|tiff?|avif|heic|heif|mp[34]|avi|mov|wmv|flv|mkv|wav|ogg|flac'
    r'|zip|tar|gz|rar|7z|bz2|exe|dll|so|dylib|bin|dat|tmp|bak|swp'
    r'|docx?|xlsx?|pptx?|csv|tsv|xml|json|yaml|yml|toml|ini|cfg|conf'
    r'|db|sqlite|log|css|js|mjs|wasm|map|class|pyc|pyo)\b'
    r'[a-zA-Z]{1,63}'
)

# Phone regex — more specific patterns first
PHONE_PATTERNS: list[str] = [
    r'\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\d\s\-]{6,}\d',
    r'\(?\d{2,4}\)?[\s\-]?\d{2,3}[\s\-]?\d{2,3}[\s\-]?\d{2,4}',
    r'8\s?\(?\d{3,4}\)?[\d\s\-]{6,}\d',
]

MIN_PHONE_DIGITS: int = 10
MAX_PHONE_DIGITS: int = 13

# Nearby keywords that indicate a phone number is genuine
PHONE_CONTEXT_KEYWORDS: list[str] = [
    "tel", "phone", "call", "fax", "mobile", "cell",
    "telephone", "hotline", "helpline", "callback",
    "контакт", "телефон", "звоните", "позвоните", "факс",
    "تماس", "تلفن", "فکس",
    "kontakt", "telefon", "anruf", "fax",
    "contact", "téléphone", "appelez", "fax",
    "contacto", "teléfono", "llame", "fax",
    "联系", "电话", "传真", "拨打",
]

# Streamlit URL limit
MAX_URLS_STREAMLIT: int = 500
