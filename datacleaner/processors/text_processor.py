"""Plain text processor."""

from pathlib import Path


def process_text(filepath: str | Path) -> str:
    """Read a plain text file and return its contents.

    Supports: .txt, .md, .json, .xml, .html, .log, .csv (raw),
              and any other text-based file.
    """
    encodings = ["utf-8", "latin-1", "cp1252", "gbk", "gb2312"]

    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue

    # Last resort: read as binary and decode with replacements
    with open(filepath, "rb") as f:
        raw = f.read()
    return raw.decode("utf-8", errors="replace")
