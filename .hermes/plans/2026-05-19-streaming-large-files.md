# P0: Streaming Mode for Large Files (>100MB)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Enable DataCleaner to process files of any size without OOM, by replacing all in-memory full-file reads with streaming/chunked processing.

**Architecture:** Add a `StreamingProcessor` base class with chunked I/O. Retrofit `scrub_dump` (CSV/SQL/JSON), `dc scan` (text/CSV), and `_apply_redactions` to use streaming. Keep the existing API backward-compatible — small files still use the fast path.

**Tech Stack:** Python stdlib (csv, json, io, itertools), ijson for streaming JSON (optional dep).

---

## Root Cause

5 locations load entire files into memory:

| File | Line | Code | Impact |
|------|------|------|--------|
| `commands/scrub_dump.py` | 319 | `rows = list(reader)` | CSV dump → OOM |
| `commands/scrub_dump.py` | 559 | `content = f.read()` | SQL dump → OOM |
| `processors/text_processor.py` | 17 | `f.read()` | Text scan → OOM |
| `processors/csv_processor.py` | 24 | `reader` → concatenated string | CSV scan → OOM |
| `cli.py` | 273 | `filepath.read_text()` | Redaction write → OOM |

`config.py` defines `max_file_size_mb: 100` but it's never checked.

---

## Architecture Decision

**Two-path strategy (keep fast path for small files):**

```
file → size check → <100MB? → fast path (existing, in-memory)
                  → ≥100MB? → stream path (new, chunked)
```

Streaming path uses fixed 10MB read buffer per chunk, processes incrementally.

---

## Task 1: Add file size gate to CLI entry points

**Objective:** Enforce `max_file_size_mb` check at scan/scrub-dump entry, route to streaming path for large files

**Files:**
- Modify: `datacleaner/cli.py:127-149` (scan command entry)
- Modify: `datacleaner/cli.py:422-446` (scrub_dump command entry)
- Modify: `datacleaner/config.py:8-33` (add streaming config)

**Step 1: Add streaming config defaults**

```python
# In DEFAULT_CONFIG dict in config.py, add under "scanning":
"streaming": {
    "chunk_rows": 10000,         # rows per chunk for CSV
    "chunk_bytes": 10_485_760,   # 10MB read buffer for text
    "auto_threshold_mb": 100,    # switch to streaming above this
}
```

**Step 2: Write failing test**

Create `tests/test_streaming.py`:

```python
import tempfile
from pathlib import Path
from datacleaner.config import load_config

def test_streaming_config_defaults():
    """Streaming config keys must exist with sensible defaults."""
    config = load_config()
    assert "streaming" in config
    assert config["streaming"]["chunk_rows"] == 10000
    assert config["streaming"]["chunk_bytes"] == 10_485_760
    assert config["streaming"]["auto_threshold_mb"] == 100

def test_file_size_gate_triggers(tmp_path):
    """Files > auto_threshold_mb should route to streaming."""
    from datacleaner.utils import StreamingRouter

    # Create a small file (should NOT trigger streaming)
    small = tmp_path / "small.csv"
    small.write_text("a,b\n1,2\n" * 10)

    router = StreamingRouter(threshold_mb=1)
    assert not router.should_stream(small)

    # Create a large file (SHOULD trigger streaming)
    large = tmp_path / "large.csv"
    # 2MB file
    large.write_bytes(b"x" * (2 * 1024 * 1024))
    assert router.should_stream(large)
```

**Step 3: Run to verify failure**

```bash
cd /mnt/g/DeepSeek-Prodects/DataCleaner-PII脱敏工具
python -m pytest tests/test_streaming.py -v
```

Expected: FAIL — `StreamingRouter` not defined.

**Step 4: Implement StreamingRouter**

Create `datacleaner/streaming.py`:

```python
"""Streaming mode router and chunked I/O primitives."""

from pathlib import Path

_MEGABYTE = 1024 * 1024


class StreamingRouter:
    """Decides whether a file should use streaming or in-memory processing."""

    def __init__(self, threshold_mb: int = 100):
        self.threshold_bytes = threshold_mb * _MEGABYTE

    def should_stream(self, filepath: Path) -> bool:
        """Return True if file exceeds the streaming threshold."""
        try:
            return filepath.stat().st_size > self.threshold_bytes
        except OSError:
            return False  # can't stat? assume small
```

**Step 5: Run to verify pass**

```bash
python -m pytest tests/test_streaming.py -v
```

**Step 6: Commit**

```bash
git add datacleaner/config.py datacleaner/streaming.py tests/test_streaming.py
git commit -m "feat: add streaming config defaults + StreamingRouter"
```

---

## Task 2: Streaming CSV reader (chunked DictReader)

**Objective:** Build a generator that yields batches of dicts from CSV without loading entire file

**Files:**
- Create: `datacleaner/utils/streaming_readers.py`
- Test: `tests/test_streaming.py` (add tests)

**Step 1: Write failing test**

```python
def test_csv_streaming_reader(tmp_path):
    """csv_chunked_reader should yield batches of N rows."""
    from datacleaner.utils.streaming_readers import csv_chunked_reader

    # Create CSV with 25 data rows + header
    csv_path = tmp_path / "test.csv"
    lines = ["name,email,phone"]
    for i in range(25):
        lines.append(f"user{i},u{i}@test.com,555-{i:04d}")
    csv_path.write_text("\n".join(lines))

    headers = []
    chunks = []
    for h, batch in csv_chunked_reader(csv_path, chunk_size=10):
        headers = h
        chunks.append(batch)

    assert headers == ["name", "email", "phone"]
    assert len(chunks) == 3  # 25 rows / 10 = 3 chunks
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5
    assert chunks[0][0] == {"name": "user0", "email": "u0@test.com", "phone": "555-0000"}
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_streaming.py::test_csv_streaming_reader -v
```

Expected: FAIL — `csv_chunked_reader` not defined.

**Step 3: Implement**

```python
"""Streaming readers for CSV, JSON, SQL — chunked I/O."""

import csv
from pathlib import Path
from typing import Iterator


def csv_chunked_reader(
    filepath: Path,
    chunk_size: int = 10000,
    encoding: str = "utf-8",
) -> Iterator[tuple[list[str], list[dict]]]:
    """Read CSV in chunks, yielding (headers, batch_of_rows).

    Each call yields up to chunk_size rows. First yield includes headers.
    """
    with open(filepath, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        batch = []
        for row in reader:
            batch.append(dict(row))
            if len(batch) >= chunk_size:
                yield headers, batch
                batch = []
        if batch:
            yield headers, batch
```

**Step 4: Run to verify pass**

**Step 5: Commit**

---

## Task 3: Streaming text reader (chunked with overlap)

**Objective:** Build chunked text reader with configurable overlap for LLM context continuity

**Files:**
- Modify: `datacleaner/utils/streaming_readers.py` (add `text_chunked_reader`)
- Test: `tests/test_streaming.py`

**Step 1: Write failing test**

```python
def test_text_chunked_reader(tmp_path):
    """text_chunked_reader yields overlapping chunks by byte boundary."""
    from datacleaner.utils.streaming_readers import text_chunked_reader

    # 50 chars of text
    text = "ABCDEFGHIJ" * 5  # 50 chars
    txt_path = tmp_path / "test.txt"
    txt_path.write_text(text)

    chunks = list(text_chunked_reader(txt_path, chunk_bytes=20, overlap_bytes=5))

    # 50 bytes / (20-5) = ~4 chunks
    assert len(chunks) == 4
    # Chunk 1: bytes 0-19
    assert len(chunks[0]) == 20
    # Chunk 2: bytes 15-34 (5 byte overlap)
    assert chunks[1][:5] == text[15:20]
```

**Step 2-5: Implement, verify, commit**

```python
def text_chunked_reader(
    filepath: Path,
    chunk_bytes: int = 10_485_760,  # 10MB
    overlap_bytes: int = 200,
    encoding: str = "utf-8",
) -> Iterator[str]:
    """Read text file in overlapping chunks for streaming PII detection.

    Yields text chunks of ~chunk_bytes with overlap_bytes of context
    carried over from the previous chunk. This ensures PII spanning
    chunk boundaries is detectable.
    """
    with open(filepath, "rb") as f:
        carry = b""
        while True:
            raw = f.read(chunk_bytes)
            if not raw:
                break
            # Decode chunk + carry
            combined = carry + raw
            chunk_text = combined.decode(encoding, errors="replace")
            yield chunk_text
            # Keep last overlap_bytes as carry for next chunk
            if len(combined) > overlap_bytes:
                carry = combined[-overlap_bytes:]
            else:
                carry = combined
```

---

## Task 4: Retrofit `scrub_dump` for streaming CSV

**Objective:** Make `scrub_dump` handle large CSV files using `csv_chunked_reader`

**Files:**
- Modify: `datacleaner/commands/scrub_dump.py` (classify_columns, scrub loop, output)
- Test: `tests/test_scrub_dump.py`

**Approach: Two-pass streaming**

Pass 1: Sample first N rows for column classification (already exists as `classify_columns` — works fine, only reads `rows[:100]`).

Pass 2: Stream chunks, scrub each chunk, append to output file incrementally.

**Step 1: Write failing integration test**

```python
def test_scrub_dump_large_csv_streaming(tmp_path):
    """scrub_dump should process a CSV > 1MB without OOM."""
    from datacleaner.commands.scrub_dump import scrub_dump

    # Generate ~2MB CSV with emails
    csv_path = tmp_path / "large.csv"
    with open(csv_path, "w") as f:
        f.write("id,name,email\n")
        for i in range(50000):
            f.write(f"{i},User{i},user{i}@example.com\n")

    result = scrub_dump(
        str(csv_path),
        output_path=str(tmp_path / "out.csv"),
        dump_format="csv",
    )

    assert result["total_rows"] == 50000
    assert "email" in result["sensitive_columns"]
    assert result["total_cells_scrubbed"] > 0
```

**Step 2-4: Implement streaming in scrub_dump, verify pass**

Key change in `scrub_dump()`:

```python
# After classification (which can stay in-memory on the sample),
# switch to streaming for the actual scrub:

# --- Stream scrub ---
output_fh = open(output_path, "w", encoding="utf-8", newline="")
writer = None

for headers, batch in csv_chunked_reader(input_path, chunk_size=10000):
    if writer is None:
        writer = csv.DictWriter(output_fh, fieldnames=headers)
        writer.writeheader()

    for row in batch:
        for header in sensitive_cols:
            value = str(row.get(header, ""))
            if value.strip():
                pii_type = _get_pii_type_for_cell(value) or "generic"
                row[header] = _generate_fake_value(value, pii_type)
                total_cells_scrubbed += 1

    writer.writerows(batch)

output_fh.close()
```

**Step 5: Commit**

---

## Task 5: Retrofit `_apply_redactions` for streaming text

**Objective:** Redaction output should stream-write instead of reading entire file into memory

**Files:**
- Modify: `datacleaner/cli.py:263-291` (`_apply_redactions`)
- Test: `tests/test_core.py` (add streaming redaction test)

**Approach:** Use `text_chunked_reader` to read chunks, apply findings positionally, write incrementally.

**Step 1: Write test, implement, commit**

---

## Task 6: Add `--no-stream` flag and size warnings

**Objective:** User can force in-memory mode, and gets a clear warning when streaming activates

**Files:**
- Modify: `datacleaner/cli.py` (scan/scrub-dump commands)

**Add to CLI:**
```python
@click.option("--no-stream", is_flag=True, help="Force in-memory processing (may OOM on large files)")
```

When streaming activates:
```
⚠ File is 250MB — switching to streaming mode (use --no-stream to force in-memory)
```

---

## Task 7: Run full test suite, fix regressions

```bash
cd /mnt/g/DeepSeek-Prodects/DataCleaner-PII脱敏工具
python -m pytest tests/ -v
```

**Checklist:**
- [ ] All 148 existing tests pass
- [ ] New streaming tests pass
- [ ] `dc scan` on a small file produces same output as before
- [ ] `dc scrub-dump` on a small CSV produces same output as before
- [ ] Large file (>100MB) processes without OOM

---

## Verification

```bash
# Small file: should use fast path (no regression)
dc scan tests/fixtures/sample_emails.csv

# Generate and test a 200MB CSV
python -c "
with open('/tmp/large_test.csv', 'w') as f:
    f.write('name,email,ssn\n')
    for i in range(2_000_000):
        f.write(f'User{i},user{i}@corp.com,{i:03d}-{i%100:02d}-{i%10000:04d}\n')
"
dc scrub-dump /tmp/large_test.csv -o /tmp/large_scrubbed.csv
# Expected: completes in < 5 min, ~2M rows scrubbed, no OOM
```

---

## Files Summary

| Action | File |
|--------|------|
| **Create** | `datacleaner/streaming.py` |
| **Create** | `datacleaner/utils/streaming_readers.py` |
| **Create** | `tests/test_streaming.py` |
| **Modify** | `datacleaner/config.py` |
| **Modify** | `datacleaner/commands/scrub_dump.py` |
| **Modify** | `datacleaner/cli.py` |
| **Modify** | `datacleaner/processors/text_processor.py` |

**Total: 7 files, ~300 LOC new + ~100 LOC modified**
