"""Tiered PII Masking Engine — L0 through L4.

L0 = Preserve  (keep original)
L1 = Partial   (mask middle, show edges for business use)
L2 = Tokenize  (replace with consistent token, AES-recoverable)
L3 = Full Scrub (SHA-256 irreversible)
L4 = Delete    (remove column entirely)

Modes:
  external — for public release, compliance audits  (L3-L4 heavy)
  internal — for internal teams, customer support   (L1-L2 heavy)
  admin    — authoritative, recoverable              (L2 with key)
"""

import hashlib
import json
import os
import secrets
from base64 import urlsafe_b64encode, urlsafe_b64decode
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ============================================================
#  MASKING LEVEL CONSTANTS
# ============================================================
L0_PRESERVE = "preserve"
L1_PARTIAL = "partial"
L2_TOKENIZE = "tokenize"
L3_SCRUB = "scrub"
L4_DELETE = "delete"

# Default masking levels per column type, by mode
MASKING_PRESETS = {
    "external": {
        "name": L3_SCRUB,
        "full_name": L3_SCRUB,
        "first_name": L3_SCRUB,
        "last_name": L3_SCRUB,
        "email": L3_SCRUB,
        "phone": L3_SCRUB,
        "ssn": L3_SCRUB,
        "credit_card": L3_SCRUB,
        "passport": L3_SCRUB,
        "salary": L3_SCRUB,
        "address": L3_SCRUB,
        "ip_address": L3_SCRUB,
        "dob": L3_SCRUB,
        "notes": L4_DELETE,
        "comments": L4_DELETE,
        "_default": L3_SCRUB,
    },
    "internal": {
        "name": L1_PARTIAL,
        "full_name": L1_PARTIAL,
        "first_name": L1_PARTIAL,
        "last_name": L1_PARTIAL,
        "email": L1_PARTIAL,
        "phone": L1_PARTIAL,
        "ssn": L1_PARTIAL,
        "credit_card": L1_PARTIAL,
        "passport": L1_PARTIAL,
        "salary": L1_PARTIAL,
        "address": L1_PARTIAL,
        "ip_address": L0_PRESERVE,
        "dob": L1_PARTIAL,
        "notes": L1_PARTIAL,
        "comments": L1_PARTIAL,
        "_default": L1_PARTIAL,
    },
    "admin": {
        "name": L2_TOKENIZE,
        "full_name": L2_TOKENIZE,
        "email": L2_TOKENIZE,
        "phone": L2_TOKENIZE,
        "ssn": L2_TOKENIZE,
        "credit_card": L2_TOKENIZE,
        "passport": L2_TOKENIZE,
        "salary": L0_PRESERVE,
        "address": L2_TOKENIZE,
        "ip_address": L0_PRESERVE,
        "dob": L0_PRESERVE,
        "notes": L0_PRESERVE,
        "comments": L0_PRESERVE,
        "_default": L2_TOKENIZE,
    },
}

# ============================================================
#  L1: Partial Masking (preserve business-useful edges)
# ============================================================

def mask_partial(value: str, pii_type: str = "generic") -> str:
    """Mask middle of value, show edges for identification.

    Rules:
      email:    show first 3 + domain      sar***@***.com
      phone:    show last 4 digits          +1-***-****
      ssn:      show last 4                  ***-**-6789
      credit:   show last 4                 ****-****-****-1234
      name:     show first 2 and last 2     Sa***on
      address:  show first 20 chars         742 Evergreen Terr***
      generic:  show first 4, mask rest     Sara***
    """
    if not value or not value.strip():
        return value

    if pii_type in ("email",):
        if "@" in value:
            local, domain = value.rsplit("@", 1)
            masked_local = local[:3] + "***" if len(local) > 3 else local[0] + "***"
            return f"{masked_local}@{domain}"
        return value[:3] + "***"

    elif pii_type in ("phone_us", "phone_uk", "phone_intl", "phone_cn"):
        # Show country code + last 4 digits
        digits = ''.join(c for c in value if c.isdigit())
        if len(digits) >= 4:
            return value[:3] + "-***-***" if "-" in value else value[:len(value)-4] + "****"
        return value[:len(value)//2] + "****"

    elif pii_type in ("ssn",):
        if len(value) >= 4:
            return "***-**-" + value[-4:]

    elif pii_type in ("credit_card",):
        clean = value.replace(" ", "").replace("-", "")
        if len(clean) >= 4:
            prefix = clean[:1]
            suffix = clean[-4:]
            middle = "****-****-****"
            return f"{prefix}{'*' * (len(clean) - 5)}-{suffix}"

    elif pii_type in ("name", "person_name"):
        parts = value.split()
        if len(parts) >= 2:
            masked = []
            for p in parts:
                if len(p) <= 2:
                    masked.append(p)
                else:
                    masked.append(p[:2] + "*" * (len(p) - 2))
            return " ".join(masked)
        return value[:2] + "*" * max(1, len(value) - 2)

    elif pii_type in ("address",):
        if len(value) > 20:
            return value[:20] + "***"
        return value[:max(len(value)//2, 5)] + "***"

    elif pii_type in ("passport", "cn_id", "ni_uk"):
        if len(value) >= 4:
            return "*" * (len(value) - 4) + value[-4:]

    elif pii_type in ("dob", "date_of_birth", "birth_date"):
        # Show year only
        parts = value.replace("/", "-").split("-")
        if len(parts) == 3:
            return "****-**-" + parts[0]

    elif pii_type in ("salary", "income", "wage"):
        return "***"  # Never show salary

    elif pii_type in ("ipv4",):
        parts = value.split(".")
        if len(parts) == 4:
            return parts[0] + ".***.***.***"
        return value[:len(value)//2] + "***"

    # Generic: show first 4 chars
    if len(value) > 4:
        return value[:4] + "*" * min(len(value) - 4, 10)
    return value[0] + "*" * (len(value) - 1)


# ============================================================
#  L2: Tokenization (AES-256-GCM recoverable)
# ============================================================

TOKEN_SALT_LEN = 16
AES_NONCE_LEN = 12
PBKDF2_ITERATIONS = 600_000

class TokenVault:
    """Encrypted mapping of real_value -> token.

    The vault is symmetrically encrypted with a password-derived key.
    Recovery requires the password.
    """

    def __init__(self, password: str):
        self.password = password
        self._mapping: dict[str, str] = {}          # token -> real_value
        self._reverse: dict[str, str] = {}          # real_value -> token
        self._counter = 0

    def tokenize(self, real_value: str, pii_type: str) -> str:
        """Replace value with a deterministic token. Stores mapping."""
        if real_value in self._reverse:
            return self._reverse[real_value]

        self._counter += 1
        # Create a deterministic but unique token
        h = hashlib.sha256(f"{pii_type}:{real_value}:{self._counter}".encode()).hexdigest()[:8]

        if pii_type in ("email",):
            token = f"tok_{h}@masked.local"
        elif pii_type in ("phone_us", "phone_uk", "phone_intl"):
            token = f"+1-555-{h[:4]}"
        elif pii_type in ("ssn",):
            token = f"XXX-XX-{h[:4]}"
        elif pii_type in ("credit_card",):
            token = f"TOK-CC-{h}"
        elif pii_type in ("name", "person_name", "full_name"):
            token = f"Person_{h}"
        else:
            token = f"TOK_{h}"

        self._mapping[token] = real_value
        self._reverse[real_value] = token
        return token

    def recover(self, token: str) -> str | None:
        """Recover original value from token."""
        return self._mapping.get(token)

    def export_encrypted(self) -> str:
        """Export vault as AES-256-GCM encrypted base64 string."""
        key = _derive_key(self.password)
        aesgcm = AESGCM(key)
        nonce = os.urandom(AES_NONCE_LEN)
        plaintext = json.dumps(self._mapping, ensure_ascii=False).encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        payload = nonce + ciphertext
        return urlsafe_b64encode(payload).decode()

    @classmethod
    def import_encrypted(cls, password: str, data: str) -> "TokenVault":
        """Decrypt and load vault from encrypted string."""
        key = _derive_key(password)
        aesgcm = AESGCM(key)
        payload = urlsafe_b64decode(data.encode())
        nonce = payload[:AES_NONCE_LEN]
        ciphertext = payload[AES_NONCE_LEN:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        mapping = json.loads(plaintext.decode())
        vault = cls(password)
        vault._mapping = mapping
        vault._reverse = {v: k for k, v in mapping.items()}
        return vault

    def save(self, path: Path) -> Path:
        """Save encrypted vault to file."""
        vault_path = Path(str(path) + ".vault")
        encrypted = self.export_encrypted()
        vault_path.write_text(encrypted)
        return vault_path

    @classmethod
    def load(cls, password: str, path: Path) -> "TokenVault":
        """Load encrypted vault from file."""
        encrypted = path.read_text()
        return cls.import_encrypted(password, encrypted)


def _derive_key(password: str) -> bytes:
    """Derive AES-256 key from password using PBKDF2."""
    salt = b"datacleaner-vault-v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode())


# ============================================================
#  L3: Full Scrub (SHA-256, irreversible)
# ============================================================

def mask_full(value: str, pii_type: str = "generic") -> str:
    """SHA-256 irreversible anonymization. Deterministic."""
    if not value:
        return value
    h = hashlib.sha256(f"dc-scrub-v1:{pii_type}:{value}".encode()).hexdigest()[:12]

    if pii_type in ("email",):
        return f"anon_{h}@scrubbed.local"
    elif pii_type in ("phone_us", "phone_uk", "phone_intl", "phone_cn"):
        return f"+1-555-{h[:4]}"
    elif pii_type in ("ssn",):
        return f"XXX-XX-{h[:4]}"
    elif pii_type in ("credit_card",):
        return f"XXXX-XXXX-XXXX-{h[:4]}"
    elif pii_type in ("name", "person_name", "full_name"):
        return f"Person_{h}"
    elif pii_type in ("ipv4",):
        if value.startswith(("192.168.", "10.", "172.16.")):
            return value
        return f"10.{int(h[:2], 16)}.{int(h[2:4], 16)}.{int(h[4:6], 16)}"
    else:
        return f"[SCRUBBED:{h}]"


# ============================================================
#  Masking Dispatcher
# ============================================================

def apply_mask(
    value: str,
    pii_type: str,
    level: str,
    vault: TokenVault | None = None,
) -> tuple[str, bool]:
    """Apply the appropriate mask for a cell.

    Returns (masked_value, deleted). If deleted=True, column should be removed.
    """
    if level == L0_PRESERVE:
        return value, False
    elif level == L1_PARTIAL:
        return mask_partial(value, pii_type), False
    elif level == L2_TOKENIZE:
        if vault is None:
            raise ValueError("L2 Tokenize requires a TokenVault")
        return vault.tokenize(value, pii_type), False
    elif level == L3_SCRUB:
        return mask_full(value, pii_type), False
    elif level == L4_DELETE:
        return "", True  # signal to delete column
    return value, False


def get_masking_level(column_name: str, mode: str) -> str:
    """Get the masking level for a column based on the mode preset."""
    preset = MASKING_PRESETS.get(mode, MASKING_PRESETS["internal"])
    return preset.get(column_name.lower(), preset["_default"])
