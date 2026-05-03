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

        if style == "block":
            replacement = "[REDACTED]"
        elif style == "placeholder":
            replacement = f"[{f.get('type', 'PII').upper()}]"
        elif style == "mask":
            replacement = "X" * match_len
        else:
            replacement = "[REDACTED]"

        # Replace characters
        result[start:end] = list(replacement)

    return "".join(result)


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
