"""Redaction engine — applies PII findings to produce clean output."""

import json
from pathlib import Path
from datetime import datetime


def redact_text(text: str, findings: list[dict], style: str = "block") -> str:
    """Apply redactions to text.

    Args:
        text: Original text
        findings: List of PII findings with start/end positions
        style:
            "block" — replace with [REDACTED]
            "placeholder" — replace with [TYPE: original length]
            "mask" — replace with X characters, preserving length
            "partial" — mask middle, preserve edges for analytics

    Returns:
        Redacted text
    """
    if not findings:
        return text

    # Sort findings by position (reverse for safe string replacement)
    findings_sorted = sorted(findings, key=lambda f: f["start"], reverse=True)

    result = list(text)

    for f in findings_sorted:
        start = f["start"]
        end = min(f["end"], len(text))
        match_len = end - start
        original = "".join(result[start:end])
        pii_type = f.get("type", "generic")

        if style == "block":
            replacement = "[REDACTED]"
        elif style == "placeholder":
            replacement = f"[{pii_type.upper()}]"
        elif style == "mask":
            replacement = "X" * match_len
        elif style == "partial":
            replacement = _partial_mask(original, pii_type)
        else:
            replacement = "[REDACTED]"

        # Replace characters
        result[start:end] = list(replacement)

    return "".join(result)


def _partial_mask(value: str, pii_type: str) -> str:
    """Mask the middle of a PII value, preserving edges for analytics.

    Strategy by type:
        email     → j***h@domain.com       (first+last char, domain visible)
        phone     → 555-***-1234            (area code + last 4)
        ssn/id    → ***-**-1234             (last 4 visible)
        credit    → ****-****-****-1234     (last 4 visible)
        name      → J*** S***               (initials)
        generic   → a***z                   (first+last char)
    """
    if pii_type in ("email",):
        # Preserve first char, last char before @, and entire domain
        if "@" in value:
            local, domain = value.split("@", 1)
            if len(local) <= 2:
                masked_local = local[0] + "*" * (len(local) - 1)
            else:
                masked_local = local[0] + "*" * max(len(local) - 2, 1) + local[-1]
            return f"{masked_local}@{domain}"
        return _mask_middle(value)

    elif pii_type in ("phone_us", "phone_uk", "phone_intl", "phone_cn", "phone"):
        # Keep area code / prefix visible, mask middle digits
        digits_only = "".join(c for c in value if c.isdigit())
        if len(digits_only) >= 6:
            # Show first 3 and last 3 digits
            masked = digits_only[:3] + "*" * (len(digits_only) - 6) + digits_only[-3:]
            # Re-apply formatting from original
            result = []
            di = 0
            for ch in value:
                if ch.isdigit():
                    result.append(masked[di] if di < len(masked) else ch)
                    di += 1
                else:
                    result.append(ch)
            return "".join(result)
        return _mask_middle(value)

    elif pii_type in ("ssn", "ni_uk", "cn_id"):
        # Show only last 4
        digits = "".join(c for c in value if c.isdigit())
        if len(digits) >= 4:
            return "*" * (len(digits) - 4) + digits[-4:]
        return _mask_middle(value)

    elif pii_type in ("credit_card",):
        # Show last 4, mask rest with format
        digits = "".join(c for c in value if c.isdigit())
        if len(digits) >= 4:
            masked = "*" * (len(digits) - 4) + digits[-4:]
            # Format as XXXX-XXXX-XXXX-1234
            groups = [masked[i:i+4] for i in range(0, len(masked), 4)]
            return "-".join(groups)
        return _mask_middle(value)

    elif pii_type in ("name", "person_name"):
        # Show initials, mask rest
        parts = value.split()
        masked_parts = []
        for part in parts:
            if len(part) <= 2:
                masked_parts.append(part[0] + "*" * (len(part) - 1))
            else:
                masked_parts.append(part[0] + "*" * (len(part) - 1))
        return " ".join(masked_parts)

    elif pii_type in ("ipv4", "ipv6"):
        # Show first octet, mask rest
        if "." in value:
            parts = value.split(".")
            return parts[0] + ".*.*.*"
        return _mask_middle(value)

    elif pii_type in ("address", "location"):
        # Keep first word visible
        parts = value.split(None, 1)
        if parts:
            return parts[0] + " ***" if len(parts) > 1 else "***"
        return "***"

    else:
        # Generic: first and last char visible
        return _mask_middle(value)


def _mask_middle(value: str) -> str:
    """Simple middle masking: first and last char visible."""
    if len(value) <= 2:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


def generate_audit_log(
    filepath: str,
    findings: list[dict],
    stats: dict,
    style: str,
) -> dict:
    """Generate an audit log entry for compliance purposes.

    Returns a dict ready for JSON serialization.
    """
    summary_findings = []
    for f in findings:
        summary_findings.append({
            "category": f["category"],
            "type": f["type"],
            "start": f["start"],
            "end": f["end"],
            "method": f["method"],
            "confidence": f.get("confidence", 1.0),
            # DO NOT include the actual matched text in audit logs
            # — that would defeat the purpose of redaction
        })

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "file": filepath,
        "redaction_style": style,
        "total_findings": stats["total"],
        "by_category": stats["by_category"],
        "by_method": stats["by_method"],
        "scanned_chars": stats.get("scanned_chars", 0),
        "findings": summary_findings,
    }


def save_audit_log(audit_data: dict, filepath: str | Path) -> Path:
    """Save audit log to disk."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False)

    return filepath


def get_audit_path(original_file: str | Path, audit_dir: str | Path) -> Path:
    """Generate a unique audit log filename."""
    original_file = Path(original_file)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = original_file.stem.replace(" ", "_")[:50]
    return Path(audit_dir) / f"audit_{safe_name}_{timestamp}.json"
