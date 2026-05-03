"""PII detection patterns — international coverage."""

import re

# ============================================================
#  EMAIL
# ============================================================
EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# ============================================================
#  CREDIT CARDS (Luhn-checkable, but we just pattern-match)
# ============================================================
_CC_DIGITS = r'[ -]?'
CREDIT_CARD = re.compile(
    r'\b(?:4[0-9]{3}' + _CC_DIGITS + r'[0-9]{4}' + _CC_DIGITS + r'[0-9]{4}' + _CC_DIGITS + r'[0-9]{4}'  # Visa
    r'|5[1-5][0-9]{2}' + _CC_DIGITS + r'[0-9]{4}' + _CC_DIGITS + r'[0-9]{4}' + _CC_DIGITS + r'[0-9]{4}'  # MasterCard
    r'|3[47][0-9]{2}' + _CC_DIGITS + r'[0-9]{6}' + _CC_DIGITS + r'[0-9]{5}'                               # Amex
    r'|6(?:011|5[0-9]{2})' + _CC_DIGITS + r'[0-9]{4}' + _CC_DIGITS + r'[0-9]{4}' + _CC_DIGITS + r'[0-9]{4}'  # Discover
    r')\b'
)

# ============================================================
#  PHONE NUMBERS
# ============================================================
# US/Canada
PHONE_US = re.compile(
    r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
)
# UK
PHONE_UK = re.compile(
    r'\b(?:\+44[-.\s]?|0)7\d{3}[-.\s]?\d{6}\b'
)
# EU general / international
PHONE_INTL = re.compile(
    r'\b\+[1-9]\d{1,3}[-.\s]?\d{1,14}(?:[-.\s]?\d{1,13})?\b'
)
# China mobile
PHONE_CN = re.compile(r'\b1[3-9]\d{9}\b')

# ============================================================
#  NATIONAL IDS
# ============================================================
# US SSN
SSN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
# UK National Insurance Number
NI_UK = re.compile(r'\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b', re.IGNORECASE)
# China ID (18 digits)
CN_ID = re.compile(r'\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b')

# ============================================================
#  IP ADDRESSES
# ============================================================
IPV4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
IPV6 = re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b')

# ============================================================
#  PASSPORT NUMBERS (generic patterns)
# ============================================================
PASSPORT_US = re.compile(r'\b[A-Z]\d{8}\b')
PASSPORT_UK = re.compile(r'\b\d{9}\b')
PASSPORT_GENERIC = re.compile(r'\b[A-Z]{1,2}\d{6,9}\b')

# ============================================================
#  BANK / IBAN / SWIFT
# ============================================================
IBAN = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b')
SWIFT = re.compile(r'\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b')

# ============================================================
#  API KEYS / TOKENS
# ============================================================
API_KEY = re.compile(
    r'\b(?:sk-[A-Za-z0-9]{20,}|'
    r'ghp_[A-Za-z0-9]{36}|'
    r'AKIA[0-9A-Z]{16}|'
    r'AIza[0-9A-Za-z\-_]{35}|'
    r'(?:api[_-]?key|apikey|secret|token|password|passwd)'
    r'\s*[:=]\s*["\']?[A-Za-z0-9_\-+=\/]{8,})["\']?'
    r'\b', re.IGNORECASE
)

# ============================================================
#  POSTAL CODES
# ============================================================
ZIP_US = re.compile(r'\b\d{5}(?:-\d{4})?\b')
POSTCODE_UK = re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b', re.IGNORECASE)

# ============================================================
#  COMPOSITE: All patterns grouped by category
# ============================================================
PATTERNS = {
    "CONTACT": {
        "email": EMAIL,
        "phone_us": PHONE_US,
        "phone_uk": PHONE_UK,
        "phone_intl": PHONE_INTL,
        "phone_cn": PHONE_CN,
    },
    "IDENTITY": {
        "ssn": SSN,
        "ni_uk": NI_UK,
        "cn_id": CN_ID,
        "passport_us": PASSPORT_US,
        "passport_uk": PASSPORT_UK,
        "passport_generic": PASSPORT_GENERIC,
    },
    "FINANCIAL": {
        "credit_card": CREDIT_CARD,
        "iban": IBAN,
        "swift": SWIFT,
    },
    "TECHNICAL": {
        "ipv4": IPV4,
        "ipv6": IPV6,
        "api_key": API_KEY,
    },
    "LOCATION": {
        "zip_us": ZIP_US,
        "postcode_uk": POSTCODE_UK,
    },
}


def get_all_patterns() -> dict:
    """Flatten pattern dict to {name: compiled_regex}."""
    flat = {}
    for category, patterns in PATTERNS.items():
        for name, pattern in patterns.items():
            flat[f"{category}/{name}"] = pattern
    return flat
