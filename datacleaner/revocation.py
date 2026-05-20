"""Offline key revocation list.

Stores SHA-256 hashes of revoked license key payloads (not the full keys).
Shipped with the software. Updated with each release.

Security: storing hashes rather than full keys means even if the
revocation list is extracted, valid keys cannot be reconstructed.
"""

import hashlib
import json
from pathlib import Path
from datetime import date

REVOKED_KEYS_FILE = Path(__file__).parent / "revoked_keys.json"


def _hash_payload(payload_b64: str) -> str:
    """Hash the base64-encoded key payload for comparison."""
    return hashlib.sha256(f"revocation-v1:{payload_b64}".encode()).hexdigest()


def load_revoked() -> set[str]:
    """Load the set of revoked key payload hashes."""
    if not REVOKED_KEYS_FILE.exists():
        return set()
    try:
        data = json.loads(REVOKED_KEYS_FILE.read_text())
        return set(data.get("revoked", []))
    except (json.JSONDecodeError, KeyError):
        return set()


def is_revoked(key: str) -> bool:
    """Check if a license key has been revoked.

    Extracts the payload portion (between prefix and checksum),
    hashes it, and checks against the revocation list.
    """
    # Extract payload: everything after DCP-/DCT- and before the checksum
    for prefix in ("DCP-", "DCT-"):
        if key.startswith(prefix):
            encoded = key[len(prefix):]
            if ":" in encoded:
                payload_b64 = encoded.rsplit(":", 1)[0]
                payload_hash = _hash_payload(payload_b64)
                revoked = load_revoked()
                return payload_hash in revoked
    return False


def add_revoked_key(key: str, reason: str = "") -> dict:
    """Add a key to the revocation list.

    Args:
        key: Full license key (DCP-xxxx:yyyy or DCT-xxxx:yyyy)
        reason: Human-readable reason (e.g., 'Refund order #GUM-123')

    Returns:
        dict with status and payload_hash
    """
    for prefix in ("DCP-", "DCT-"):
        if key.startswith(prefix):
            encoded = key[len(prefix):]
            if ":" in encoded:
                payload_b64 = encoded.rsplit(":", 1)[0]
                payload_hash = _hash_payload(payload_b64)

                # Load existing
                data = {}
                if REVOKED_KEYS_FILE.exists():
                    try:
                        data = json.loads(REVOKED_KEYS_FILE.read_text())
                    except json.JSONDecodeError:
                        data = {"version": 1, "revoked": []}

                if "revoked" not in data:
                    data["revoked"] = []

                # Check if already revoked
                if payload_hash in data["revoked"]:
                    return {"status": "already_revoked", "hash": payload_hash}

                # Add
                data["revoked"].append(payload_hash)
                data["version"] = data.get("version", 0) + 1
                data["updated"] = date.today().isoformat()

                # Add reason to metadata if provided
                if "reasons" not in data:
                    data["reasons"] = {}
                data["reasons"][payload_hash] = reason

                REVOKED_KEYS_FILE.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False) + "\n"
                )

                return {
                    "status": "revoked",
                    "hash": payload_hash,
                    "reason": reason,
                    "total_revoked": len(data["revoked"]),
                }

    return {"status": "invalid_key_format"}


def revoke_batch(keys: list[tuple[str, str]]) -> list[dict]:
    """Revoke multiple keys at once.

    Args:
        keys: List of (key, reason) tuples
    """
    results = []
    for key, reason in keys:
        results.append(add_revoked_key(key, reason))
    return results
