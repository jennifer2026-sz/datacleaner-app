"""Streaming readers for CSV, text — chunked I/O.

Replaces full-file reads with incremental, memory-bounded generators.
Used by scan and scrub-dump when files exceed the streaming threshold.
"""

import csv
from pathlib import Path
from typing import Iterator, Sequence


def csv_chunked_reader(
    filepath: str | Path,
    chunk_size: int = 10000,
    encoding: str = "utf-8",
) -> Iterator[tuple[Sequence[str], list[dict]]]:
    """Read CSV in batches, yielding (headers, batch_of_rows).

    Each batch contains at most chunk_size rows. The first batch for
    a file includes the headers; subsequent batches reuse the same
    headers (for compatibility with callers that need them per-batch).

    Args:
        filepath: Path to CSV file.
        chunk_size: Max rows per yielded batch.
        encoding: Text encoding for the file.

    Yields:
        Tuple of (headers: list[str], rows: list[dict[str, str]])
    """
    filepath = Path(filepath)

    # Try the requested encoding, fall back to common ones
    encodings_to_try = [encoding, "utf-8", "latin-1", "cp1252", "gbk"]
    seen: set[str] = set()

    for enc in encodings_to_try:
        if enc in seen:
            continue
        seen.add(enc)
        try:
            with open(filepath, "r", encoding=enc, errors="replace", newline="") as fh:
                reader = csv.DictReader(fh)
                headers = reader.fieldnames or []

                batch: list[dict] = []
                for row in reader:
                    batch.append(dict(row))
                    if len(batch) >= chunk_size:
                        yield headers, batch
                        batch = []
                if batch:
                    yield headers, batch
            return  # success — done
        except (UnicodeDecodeError, UnicodeError):
            continue

    # Absolute last resort
    with open(filepath, "r", encoding="latin-1", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        batch: list[dict] = []
        for row in reader:
            batch.append(dict(row))
            if len(batch) >= chunk_size:
                yield headers, batch
                batch = []
        if batch:
            yield headers, batch


def text_chunked_reader(
    filepath: str | Path,
    chunk_bytes: int = 10_485_760,  # 10 MiB
    overlap_bytes: int = 200,
    encoding: str = "utf-8",
) -> Iterator[str]:
    """Read text file in overlapping chunks for streaming PII detection.

    Yields text chunks of approximately chunk_bytes. overlap_bytes from
    the end of each chunk is carried into the start of the next, ensuring
    PII that spans a chunk boundary is still detectable.

    Args:
        filepath: Path to text file.
        chunk_bytes: Approximate bytes per chunk.
        overlap_bytes: Bytes of overlap between chunks.
        encoding: Text encoding.

    Yields:
        String chunks.
    """
    filepath = Path(filepath)

    with open(filepath, "rb") as fh:
        carry = b""
        while True:
            raw = fh.read(chunk_bytes)
            if not raw:
                break

            combined = carry + raw
            chunk_text = combined.decode(encoding, errors="replace")
            yield chunk_text

            # Keep last overlap_bytes as context for the next chunk
            if len(combined) > overlap_bytes:
                carry = combined[-overlap_bytes:]
            else:
                carry = combined
