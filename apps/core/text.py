"""Persian text helpers: digit conversion, normalization for search, price formatting."""
import re
import unicodedata

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EN_DIGITS = "0123456789"

_TO_EN = str.maketrans(FA_DIGITS + AR_DIGITS, EN_DIGITS * 2)
_TO_FA = str.maketrans(EN_DIGITS, FA_DIGITS)

_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "ؤ": "و", "إ": "ا", "أ": "ا", "آ": "ا"})
_DIACRITICS = re.compile(r"[ً-ْٰـ]")  # harakat + tatweel
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


def to_en_digits(s: str) -> str:
    return (s or "").translate(_TO_EN)


def to_fa_digits(s) -> str:
    return str(s if s is not None else "").translate(_TO_FA)


def normalize(s: str) -> str:
    """Normalize Persian text for search: unify ي/ی and ك/ک, strip diacritics, unify digits,
    replace ZWNJ with space, lowercase Latin, collapse whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_ARABIC_TO_PERSIAN)
    s = _DIACRITICS.sub("", s)
    s = s.replace("‌", " ")
    s = to_en_digits(s).lower()
    s = _NON_WORD.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_int(s, default=None):
    """Parse an integer typed with Persian/Latin digits and thousands separators."""
    if s is None:
        return default
    s = to_en_digits(str(s))
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return default
    try:
        return int(s)
    except ValueError:
        return default


def format_price(n) -> str:
    """1250000 -> '۱٬۲۵۰٬۰۰۰' (Persian digits, Persian thousands separator)."""
    if n is None:
        return ""
    return to_fa_digits(f"{int(n):,}").replace(",", "٬")


PHONE_RE = re.compile(r"^09\d{9}$")


def clean_phone(raw: str):
    """Accept 09xxxxxxxxx / +989xxxxxxxxx / 00989xxxxxxxxx with any digit script; return 09xxxxxxxxx or None."""
    s = re.sub(r"[\s\-()]", "", to_en_digits(raw or ""))
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    elif len(s) == 10 and s.startswith("9"):
        s = "0" + s
    return s if PHONE_RE.match(s) else None


def mask_phone(phone: str) -> str:
    """09123456789 -> ۰۹۱۲ ۳۴۵ ۶۷۸۹ (display formatting)."""
    p = to_en_digits(phone or "")
    if len(p) == 11:
        return to_fa_digits(f"{p[:4]} {p[4:7]} {p[7:]}")
    return to_fa_digits(p)


# patterns we don't allow inside listing text (contact details / links)
CONTACT_IN_TEXT_RE = re.compile(
    r"(09\d{2}[\s\-]?\d{3}[\s\-]?\d{4})|(\+98\s?9\d{9})|(https?://)|(www\.)|(@[a-z0-9_]{4,})|(t\.me/)|(instagram)|(تلگرام)|(اینستاگرام)",
    re.IGNORECASE,
)


def has_contact_info(text: str) -> bool:
    return bool(CONTACT_IN_TEXT_RE.search(to_en_digits(text or "")))
