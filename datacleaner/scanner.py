"""Core scanner — orchestrates regex + LLM PII detection."""

import re
from pathlib import Path
from datacleaner.config import load_config
from datacleaner.detectors import detect_pii_regex, detect_pii_llm


def scan_text(text: str, use_llm: bool = True) -> dict:
    """Scan text for PII using both regex and LLM detectors.

    Args:
        text: The text to scan
        use_llm: Whether to use the LLM pass (slower but catches contextual PII)

    Returns:
        {
            "findings": [...],
            "stats": {"total": int, "by_category": {...}, "by_method": {...}},
            "scanned_chars": int,
        }
    """
    config = load_config()
    all_findings = []

    # --- Pass 1: Regex (fast) ---
    regex_findings = detect_pii_regex(text)
    all_findings.extend(regex_findings)

    # --- Pass 2: LLM (contextual, for text chunks) ---
    if use_llm:
        chunk_size = config["scanning"]["chunk_size"]
        chunk_overlap = config["scanning"]["chunk_overlap"]

        # Split text into chunks for LLM
        chunks = _chunk_text(text, chunk_size, chunk_overlap)

        for i, (chunk_start, chunk_text) in enumerate(chunks):
            try:
                llm_findings = detect_pii_llm(chunk_text)
                # Adjust positions to absolute (relative to original text)
                for f in llm_findings:
                    f["start"] += chunk_start
                    f["end"] += chunk_start
                all_findings.extend(llm_findings)
            except ConnectionError:
                raise
            except Exception:
                # LLM call failed for this chunk — continue with next
                continue

    # --- Deduplicate overlapping findings ---
    all_findings.sort(key=lambda f: (f["start"], -f["end"]))
    deduped = _deduplicate(all_findings)

    # --- Generate stats ---
    by_category = {}
    by_method = {}
    for f in deduped:
        cat = f["category"]
        method = f["method"]
        by_category[cat] = by_category.get(cat, 0) + 1
        by_method[method] = by_method.get(method, 0) + 1

    return {
        "findings": deduped,
        "stats": {
            "total": len(deduped),
            "by_category": by_category,
            "by_method": by_method,
        },
        "scanned_chars": len(text),
    }


def scan_file(filepath: str | Path, use_llm: bool = True) -> dict:
    """Scan a file for PII.

    Supports: .txt, .md, .json, .csv, .pdf, .docx, .xlsx, .log, .html
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Check file size
    size_mb = filepath.stat().st_size / (1024 * 1024)
    config = load_config()
    if size_mb > config["scanning"]["max_file_size_mb"]:
        raise ValueError(
            f"File too large: {size_mb:.1f}MB (max {config['scanning']['max_file_size_mb']}MB)"
        )

    # Dispatch to processor
    suffix = filepath.suffix.lower()
    from datacleaner.processors import (
        process_text,
        process_pdf,
        process_csv,
        process_docx,
        process_excel,
    )

    if suffix == ".pdf":
        text = process_pdf(filepath)
    elif suffix == ".csv":
        text = process_csv(filepath)
    elif suffix in (".xlsx", ".xls"):
        text = process_excel(filepath)
    elif suffix == ".docx":
        text = process_docx(filepath)
    else:
        text = process_text(filepath)

    result = scan_text(text, use_llm=use_llm)
    result["file"] = str(filepath)
    result["file_size_mb"] = round(size_mb, 2)

    return result


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[tuple[int, str]]:
    """Split text into overlapping chunks for LLM processing.

    Returns list of (start_position, chunk_text)
    """
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Prefer paragraph breaks
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Fall back to sentence boundary
                sent_break = max(
                    text.rfind(". ", start, end),
                    text.rfind(".\n", start, end),
                    text.rfind("? ", start, end),
                    text.rfind("! ", start, end),
                )
                if sent_break > start + chunk_size // 2:
                    end = sent_break + 1

        chunks.append((start, text[start:end]))
        start = end - overlap

    return chunks


def _deduplicate(findings: list[dict]) -> list[dict]:
    """Remove overlapping findings, preferring higher-confidence LLM results
    and longer matches."""
    if not findings:
        return []

    # Sort by position, then by method (LLM preferred over regex), then by length desc
    findings.sort(
        key=lambda f: (
            f["start"],
            0 if f["method"] == "llm" else 1,
            -(f["end"] - f["start"]),
        )
    )

    kept = []
    for f in findings:
        # Check overlap with already-kept findings
        overlaps = False
        for k in kept:
            if _spans_overlap(f["start"], f["end"], k["start"], k["end"]):
                overlaps = True
                break

        if not overlaps:
            kept.append(f)

    # Restore position-based sort
    kept.sort(key=lambda f: f["start"])
    return kept


def _spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Check if two character spans overlap (with 2-char tolerance)."""
    return a_start < b_end - 2 and b_start < a_end - 2
