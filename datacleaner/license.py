"""License key validation for DataCleaner CLI."""

import hashlib
import json
import time
from pathlib import Path
from datacleaner.config import CONFIG_DIR, load_config, save_config
from datacleaner.revocation import is_revoked


LICENSE_FILE = CONFIG_DIR / "license.json"


def validate_key(key: str) -> dict:
    """Validate a license key.

    In production, this would call a remote validation server.
    For the self-hosted version, we use offline key verification with
    a simple hash-based scheme.

    Returns: {"valid": bool, "tier": "free"|"pro"|"team", "expires": str|None, "message": str}
    """
    key = key.strip()

    # --- Free tier special keys ---
    if key == "FREE-TRIAL":
        return {
            "valid": True,
            "tier": "free",
            "expires": None,
            "message": "Free tier active — limited to 100 documents/month.",
        }

    # --- Pro tier key validation ---
    pro_prefix = "DCP-"
    team_prefix = "DCT-"

    if key.startswith(pro_prefix):
        payload = _decode_payload(key, pro_prefix)
        if payload and payload.get("tier") == "pro":
            if _check_expiry(payload):
                if is_revoked(key):
                    return {"valid": False, "tier": "free", "expires": None,
                            "message": "This license key has been revoked. If you believe this is an error, contact contact@getdatacleaner.com."}
                expiry_info = ""
                exp = payload.get("expires")
                if exp:
                    expiry_info = f" (expires {exp})"
                return {
                    "valid": True,
                    "tier": "pro",
                    "expires": exp,
                    "message": f"Pro license active{expiry_info}.",
                }
            else:
                return {"valid": False, "tier": "free", "expires": None, "message": "License expired."}

    if key.startswith(team_prefix):
        payload = _decode_payload(key, team_prefix)
        if payload and payload.get("tier") == "team":
            if _check_expiry(payload):
                if is_revoked(key):
                    return {"valid": False, "tier": "free", "expires": None,
                            "message": "This license key has been revoked. If you believe this is an error, contact contact@getdatacleaner.com."}
                expiry_info = ""
                exp = payload.get("expires")
                if exp:
                    expiry_info = f" (expires {exp})"
                return {
                    "valid": True,
                    "tier": "team",
                    "expires": exp,
                    "message": f"Team license active{expiry_info}.",
                }
            else:
                return {"valid": False, "tier": "free", "expires": None, "message": "License expired."}

    return {"valid": False, "tier": "free", "expires": None, "message": "Invalid license key. Get one at https://getdatacleaner.com"}


def _decode_payload(key: str, prefix: str) -> dict | None:
    """Decode and verify a license key payload."""
    try:
        encoded = key[len(prefix):]
        # Simple format: base64-like encoded JSON with checksum
        # Format: {json_payload}:{checksum}
        if ":" not in encoded:
            return None

        payload_str, checksum = encoded.rsplit(":", 1)
        expected = hashlib.sha256(f"datacleaner-salt-{payload_str}".encode()).hexdigest()[:8]

        if checksum != expected:
            return None

        return json.loads(_b64_decode(payload_str))
    except Exception:
        return None


def _check_expiry(payload: dict) -> bool:
    """Check if license has not expired."""
    expires = payload.get("expires")
    if not expires:
        return True  # No expiry = perpetual
    try:
        expiry_ts = time.mktime(time.strptime(expires, "%Y-%m-%d"))
        return time.time() < expiry_ts
    except Exception:
        return False


def _b64_decode(s: str) -> str:
    """URL-safe base64 decode."""
    import base64
    s = s.replace("-", "+").replace("_", "/")
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.b64decode(s).decode("utf-8", errors="ignore")


def activate_license(key: str) -> bool:
    """Activate and persist a license key."""
    result = validate_key(key)
    if result["valid"]:
        config = load_config()
        config["license"]["key"] = key
        config["license"]["verified"] = True
        save_config(config)

        LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LICENSE_FILE, "w") as f:
            json.dump({
                "key": key,
                "tier": result["tier"],
                "expires": result["expires"],
                "activated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }, f, indent=2)

        return True
    return False


def check_license() -> dict:
    """Check current license status. Returns validate_key() result."""
    config = load_config()
    key = config["license"].get("key", "")
    if not key:
        return {"valid": False, "tier": "free", "expires": None, "message": "No license. Free tier active (100 docs/month)."}
    return validate_key(key)
