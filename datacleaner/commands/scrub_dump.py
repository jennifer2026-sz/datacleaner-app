"""dc scrub-dump — Database dump PII scrubbing command.

Scrubs PII from database dumps (CSV, SQL INSERT dumps) with
deterministic, consistent anonymization. All processing is local —
zero data leaves the machine.

Part of Iron Legion automated cleaning pipeline.
"""

import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
from rich import box

from datacleaner.scanner import scan_text
from datacleaner.redactor import redact_text, generate_audit_log, save_audit_log, get_audit_path
from datacleaner.config import load_config

console = Console()

# Streaming: rows per batch when processing CSV via chunked reader
_STREAM_CHUNK_ROWS = 10000

# ============================================================
#  COLUMN PII CLASSIFICATION
# ============================================================

# Threshold: if > this fraction of sampled cells match PII, mark column as sensitive
PII_COLUMN_THRESHOLD = 0.3
SAMPLE_SIZE = 100  # rows to sample per column


def _hash_value(value: str, salt: str = "dc-scrub-v1") -> str:
    """Deterministic hash for consistent anonymization.

    Same input + salt → same output. Preserves uniqueness across tables.
    """
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:12]


def _generate_fake_value(value: str, pii_type: str) -> str:
    """Generate a deterministic, format-preserving fake value.

    Different PII types get different fake formats:
    - email → fake_<hash>@anonymized.local
    - phone → +1-555-<hash>
    - ssn → XXX-XX-<hash>
    - name → User_<hash>
    - credit_card → XXXX-XXXX-XXXX-<hash>
    - generic → [ANONYMIZED_<hash>]
    """
    h = _hash_value(value)

    if pii_type in ("email",):
        return f"anon_{h}@scrubbed.local"
    elif pii_type in ("phone_us", "phone_uk", "phone_intl", "phone_cn"):
        return f"+1-555-{h[:4]}"
    elif pii_type in ("ssn",):
        return f"XXX-XX-{h[:4]}"
    elif pii_type in ("credit_card",):
        return f"XXXX-XXXX-XXXX-{h[:4]}"
    elif pii_type in ("cn_id", "ni_uk"):
        return f"ID-{h[:8]}"
    elif pii_type in ("ipv4",):
        # Preserve private IPs, anonymize public ones
        if value.startswith(("192.168.", "10.", "172.16.")):
            return value  # preserve private IPs
        return f"10.{int(h[:2], 16)}.{int(h[2:4], 16)}.{int(h[4:6], 16)}"
    elif pii_type in ("iban", "swift"):
        return f"XX{h[:8]}"
    elif pii_type in ("api_key",):
        return f"sk-redacted-{h[:8]}"
    else:
        return f"[SCRUBBED:{h[:8]}]"


def detect_pii_in_cell(value: str) -> list[dict]:
    """Run PII detection on a single cell value.

    Uses regex-only for speed (LLM is too slow for per-cell analysis
    on millions of rows). Returns list of findings.
    """
    if not value or not isinstance(value, str):
        return []
    result = scan_text(value, use_llm=False)
    return result.get("findings", [])


def classify_columns(rows: list[dict], headers: list[str]) -> dict[str, bool]:
    """Sample rows and classify which columns contain PII.

    Returns {header: is_sensitive}
    """
    sample = rows[:SAMPLE_SIZE]
    column_status = {}

    for header in headers:
        pii_hits = 0
        non_empty = 0
        for row in sample:
            value = str(row.get(header, "")).strip()
            if not value:
                continue
            non_empty += 1
            findings = detect_pii_in_cell(value)
            if findings:
                pii_hits += 1

        # Mark as sensitive if hit rate exceeds threshold
        is_sensitive = (non_empty > 0 and pii_hits / non_empty >= PII_COLUMN_THRESHOLD)
        column_status[header] = is_sensitive

    return column_status


def _get_pii_type_for_cell(value: str) -> Optional[str]:
    """Determine the dominant PII type for a cell value."""
    findings = detect_pii_in_cell(value)
    if not findings:
        return None
    # Return the first finding's type
    return findings[0].get("type", "generic")


# ============================================================
#  SQL DUMP PARSER
# ============================================================

INSERT_RE = re.compile(
    r'INSERT\s+INTO\s+`?(\w+)`?\s*(?:\(([^)]+)\))?\s*VALUES\s*\((.+)\);?',
    re.IGNORECASE | re.DOTALL,
)

# Handle multi-row INSERT: VALUES (...), (...), (...)
MULTI_VALUES_RE = re.compile(r'\)\s*,\s*\(')


def _parse_sql_insert(line: str) -> Optional[dict]:
    """Parse a SQL INSERT statement into structured data.

    Returns None if not an INSERT statement.
    Returns {
        "table": str,
        "columns": [str, ...],
        "values": [[str, ...], ...]  # list of row value lists
    }
    """
    line = line.strip()
    if not line.upper().startswith("INSERT"):
        return None

    # Try to match full INSERT ... VALUES ...
    m = INSERT_RE.search(line)
    if not m:
        return None

    table = m.group(1)
    columns_str = m.group(2)
    values_str = m.group(3)

    # Parse columns
    if columns_str:
        columns = [c.strip().strip("`").strip('"') for c in columns_str.split(",")]
    else:
        columns = []

    # Parse values (handle multiple rows)
    all_rows = []

    # Check if this is a single value group or multi-value
    # Multi-value: VALUES (...), (...), (...)
    # Single-value: VALUES (...)
    # The regex may capture values with or without outer parens depending on format

    # Pre-process: normalize the values string
    # For multi-value inserts, split on '), (' boundaries
    if '),' in values_str and '(' in values_str:
        # Multi-value format: split and clean
        raw_parts = _split_value_groups(values_str)
        if raw_parts:
            for part in raw_parts:
                row_values = _parse_value_list(part)
                all_rows.append(row_values)
        else:
            # Fallback: split on '), (' pattern
            parts = []
            depth = 0
            current = []
            for ch in values_str:
                if ch == '(':
                    if depth == 0:
                        continue  # skip leading paren
                    depth += 1
                    current.append(ch)
                elif ch == ')':
                    if depth == 0:
                        parts.append(''.join(current))
                        current = []
                        continue
                    depth -= 1
                    current.append(ch)
                elif ch == ',' and depth == 0:
                    continue  # skip comma between groups
                else:
                    current.append(ch)
            if current:
                parts.append(''.join(current))
            for part in parts:
                row_values = _parse_value_list(part)
                all_rows.append(row_values)
    else:
        # Single value group
        row_values = _parse_value_list(values_str)
        all_rows.append(row_values)

    return {
        "table": table,
        "columns": columns,
        "values": all_rows,
    }


def _split_value_groups(values_str: str) -> list[str]:
    """Split VALUES (...), (...), ... respecting nested parens."""
    parts = []
    paren_depth = 0
    current = []
    i = 0

    while i < len(values_str):
        ch = values_str[i]

        if ch == "(":
            paren_depth += 1
            if paren_depth == 1:
                # Start of a new group, skip the opening paren
                i += 1
                continue
        elif ch == ")":
            paren_depth -= 1
            if paren_depth == 0:
                # End of current group
                parts.append("".join(current))
                current = []
                i += 1
                # Skip comma and whitespace
                while i < len(values_str) and values_str[i] in " ,\n\r\t":
                    i += 1
                continue

        if paren_depth >= 1:
            current.append(ch)

        i += 1

    return parts


def _parse_value_list(values_str: str) -> list[str]:
    """Parse a comma-separated value list, respecting quotes.

    Handles: 'string', NULL, 123, "quoted", etc.
    """
    values = []
    current = []
    in_quote = None  # None, "'", or '"'
    i = 0

    while i < len(values_str):
        ch = values_str[i]

        if in_quote:
            current.append(ch)
            if ch == in_quote:
                # Check for escaped quote
                if i + 1 < len(values_str) and values_str[i + 1] == in_quote:
                    current.append(values_str[i + 1])
                    i += 1
                else:
                    in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
            current.append(ch)
        elif ch == ",":
            values.append("".join(current).strip())
            current = []
        else:
            current.append(ch)

        i += 1

    # Don't forget the last value
    if current:
        values.append("".join(current).strip())

    return values


# ============================================================
#  CSV DUMP HANDLER
# ============================================================

def read_csv_dump(filepath: Path) -> tuple[list[str], list[dict]]:
    """Read CSV dump file, return (headers, rows)."""
    with open(filepath, "r", encoding="utf-8", errors="replace", newline="") as f:
        # Sniff dialect
        sample = f.read(8192)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample)
        reader = csv.DictReader(f, dialect=dialect)
        headers = reader.fieldnames or []
        rows = list(reader)

    return headers, rows


def write_csv_dump(
    filepath: Path,
    headers: list[str],
    rows: list[dict],
):
    """Write cleaned CSV dump."""
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


# ============================================================
#  MAIN SCRUB LOGIC
# ============================================================

def scrub_dump(
    input_path: str | Path,
    output_path: Optional[str | Path] = None,
    audit_dir: Optional[str | Path] = None,
    style: str = "placeholder",
    dump_format: Optional[str] = None,
    no_llm: bool = True,  # Default to regex-only for dump scrubbing (speed)
    output_json: bool = False,
) -> dict:
    """Scrub PII from a database dump file.

    Args:
        input_path: Path to dump file (.csv, .sql, .json)
        output_path: Output path (auto-generated if None)
        audit_dir: Directory for audit logs
        style: Redaction style
        dump_format: 'csv', 'sql', or None (auto-detect)
        no_llm: Use regex-only for speed (default: True)
        output_json: Output results as JSON

    Returns:
        Stats dict: {
            "total_rows": int,
            "sensitive_columns": [str, ...],
            "total_cells_scrubbed": int,
            "pii_by_column": {header: count},
        }
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    # Auto-detect format
    if dump_format is None:
        suffix = input_path.suffix.lower()
        if suffix == ".csv":
            dump_format = "csv"
        elif suffix == ".sql":
            dump_format = "sql"
        elif suffix == ".json":
            dump_format = "json"
        else:
            # Try to detect by content
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                first_line = f.readline().strip()
            if first_line.upper().startswith("INSERT") or first_line.upper().startswith("--"):
                dump_format = "sql"
            else:
                dump_format = "csv"  # default

    # Generate output path
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_scrubbed{input_path.suffix}"
    output_path = Path(output_path)

    config = load_config()
    audit_base = Path(audit_dir or config["output"]["audit_dir"]).expanduser().resolve()

    console.print(f"\n  [bold]Scrubbing dump:[/bold] [cyan]{input_path.name}[/cyan]")
    console.print(f"  Format: [cyan]{dump_format}[/cyan] | Style: [cyan]{style}[/cyan]")
    console.print()

    # --- Load data ---
    if dump_format == "csv":
        # Use streaming for CSV: classify on first chunk, then stream-scrub
        stats = _scrub_csv_streaming(
            input_path, output_path, style, audit_base,
        )
        if output_json:
            console.print("\n[JSON Output]")
            console.print(json.dumps(stats, indent=2, ensure_ascii=False))
        return stats
    elif dump_format == "json":
        import json as _json
        with open(input_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        if isinstance(data, list):
            headers = list(data[0].keys()) if data else []
            rows = data
        else:
            console.print("[red]JSON must be an array of objects.[/red]")
            sys.exit(1)
    elif dump_format == "sql":
        headers, rows = _parse_sql_dump(input_path)
    else:
        console.print(f"[red]Unsupported format: {dump_format}[/red]")
        sys.exit(1)

    if not rows:
        console.print("[yellow]No data rows found in dump.[/yellow]")
        return {"total_rows": 0, "sensitive_columns": [], "total_cells_scrubbed": 0, "pii_by_column": {}}

    if not headers and dump_format == "csv":
        # Auto-generate headers from first row
        if rows and isinstance(rows[0], dict):
            headers = list(rows[0].keys())

    console.print(f"  Rows: [cyan]{len(rows)}[/cyan] | Columns: [cyan]{len(headers)}[/cyan]")

    # --- Classify columns ---
    console.print("\n  [bold]Phase 1:[/bold] Classifying columns...")
    column_status = classify_columns(rows, headers)

    sensitive_cols = [h for h, s in column_status.items() if s]
    if not sensitive_cols:
        console.print("  [green]→ No PII-bearing columns detected.[/green]")
        # Still output the clean copy
        if dump_format == "csv":
            write_csv_dump(output_path, headers, rows)
        elif dump_format == "sql":
            _write_sql_output(output_path, rows, headers, sensitive_cols, {})
        console.print(f"\n  [green]✓ Clean copy written to:[/green] {output_path}")
        return {
            "total_rows": len(rows),
            "sensitive_columns": [],
            "total_cells_scrubbed": 0,
            "pii_by_column": {},
        }

    # Display classified columns
    col_table = Table(box=box.MINIMAL)
    col_table.add_column("Column", style="cyan")
    col_table.add_column("Status")
    col_table.add_column("PII Type", style="dim")
    for h in headers:
        if column_status[h]:
            # Sample to detect PII type
            sample_val = next((str(r.get(h, "")) for r in rows[:10] if str(r.get(h, "")).strip()), "")
            pii_type = _get_pii_type_for_cell(sample_val) or "mixed"
            col_table.add_row(h, "[red]SENSITIVE[/red]", pii_type)
        else:
            col_table.add_row(h, "[dim]clean[/dim]", "-")
    console.print(col_table)

    # --- Scrub ---
    console.print(f"\n  [bold]Phase 2:[/bold] Scrubbing {len(sensitive_cols)} sensitive column(s)...")
    pii_by_column = {}
    total_cells_scrubbed = 0

    for header in sensitive_cols:
        count = 0
        pii_type_cache = {}  # cache PII type per unique value

        for row in rows:
            value = str(row.get(header, ""))
            if not value.strip():
                continue

            # Determine PII type (cached per unique value for speed)
            if value not in pii_type_cache:
                pii_type_cache[value] = _get_pii_type_for_cell(value) or "generic"

            pii_type = pii_type_cache[value]
            if pii_type:
                row[header] = _generate_fake_value(value, pii_type)
                count += 1

        pii_by_column[header] = count
        total_cells_scrubbed += count
        console.print(f"  [green]✓[/green] {header}: [yellow]{count}[/yellow] cells scrubbed")

    # --- Write output ---
    console.print(f"\n  [bold]Phase 3:[/bold] Writing scrubbed output...")
    if dump_format == "csv":
        write_csv_dump(output_path, headers, rows)
    elif dump_format == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
    elif dump_format == "sql":
        _write_sql_output(output_path, rows, headers, sensitive_cols, pii_by_column)

    console.print(f"  [green]✓[/green] {output_path}")

    # --- Audit log ---
    audit_data = {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "input_file": str(input_path),
        "output_file": str(output_path),
        "format": dump_format,
        "style": style,
        "total_rows": len(rows),
        "total_columns": len(headers),
        "sensitive_columns": sensitive_cols,
        "total_cells_scrubbed": total_cells_scrubbed,
        "pii_by_column": pii_by_column,
        "column_classification": {h: ("SENSITIVE" if s else "clean") for h, s in column_status.items()},
    }
    audit_path = get_audit_path(input_path, audit_base)
    save_audit_log(audit_data, audit_path)
    console.print(f"  [dim]Audit: {audit_path}[/dim]")

    stats = {
        "total_rows": len(rows),
        "sensitive_columns": sensitive_cols,
        "total_cells_scrubbed": total_cells_scrubbed,
        "pii_by_column": pii_by_column,
    }

    # --- Display summary ---
    console.print()
    console.print(Panel.fit(
        f"[green]✓ Scrubbing complete[/green]\n"
        f"  {len(rows)} rows × {len(headers)} columns\n"
        f"  {len(sensitive_cols)} sensitive columns found\n"
        f"  {total_cells_scrubbed} cells anonymized\n"
        f"  Output: {output_path.name}",
        border_style="green",
    ))

    if output_json:
        console.print("\n[JSON Output]")
        console.print(json.dumps(stats, indent=2, ensure_ascii=False))

    return stats


# ============================================================
#  STREAMING CSV SCRUB
# ============================================================

def _scrub_csv_streaming(
    input_path: Path,
    output_path: Path,
    style: str,
    audit_base: Path,
) -> dict:
    """Scrub a CSV dump using streaming — never loads entire file into memory.

    Two-phase approach using a single iterator:
      1. Read first chunk → classify columns, sample PII types
      2. Continue same iterator → scrub + write incrementally
    """
    from datacleaner.utils.streaming_readers import csv_chunked_reader

    total_rows = 0
    total_cells_scrubbed = 0
    pii_by_column: dict[str, int] = {}

    # --- Create single iterator ---
    chunk_iter = csv_chunked_reader(input_path, chunk_size=_STREAM_CHUNK_ROWS)

    # Get first chunk
    try:
        headers_raw, first_chunk_rows = next(chunk_iter)
    except StopIteration:
        console.print("[yellow]No data rows found in dump.[/yellow]")
        return {"total_rows": 0, "sensitive_columns": [], "total_cells_scrubbed": 0, "pii_by_column": {}}

    if not first_chunk_rows:
        console.print("[yellow]No data rows found in dump.[/yellow]")
        return {"total_rows": 0, "sensitive_columns": [], "total_cells_scrubbed": 0, "pii_by_column": {}}

    headers: list[str] = list(headers_raw)

    # --- Phase 1: classify from first chunk ---
    console.print(f"\n  [bold]Phase 1:[/bold] Classifying columns (sampling from first {len(first_chunk_rows)} rows)...")
    column_status = classify_columns(first_chunk_rows, headers)
    sensitive_cols = [h for h, s in column_status.items() if s]

    # Display classified columns
    col_table = Table(box=box.MINIMAL)
    col_table.add_column("Column", style="cyan")
    col_table.add_column("Status")
    col_table.add_column("PII Type", style="dim")
    for h in headers:
        if column_status[h]:
            sample_val = next((str(r.get(h, "")) for r in first_chunk_rows[:10] if str(r.get(h, "")).strip()), "")
            pii_type = _get_pii_type_for_cell(sample_val) or "mixed"
            col_table.add_row(h, "[red]SENSITIVE[/red]", pii_type)
        else:
            col_table.add_row(h, "[dim]clean[/dim]", "-")
    console.print(col_table)

    # --- Phase 2: stream-scrub ---
    console.print(f"\n  [bold]Phase 2:[/bold] Scrubbing {len(sensitive_cols)} sensitive column(s) [dim](streaming)[/dim]...")

    # Open output file once — wrapped in try/finally for safety
    output_fh = open(output_path, "w", encoding="utf-8", newline="")
    try:
        writer = csv.DictWriter(output_fh, fieldnames=headers)
        writer.writeheader()

        if not sensitive_cols:
            # No PII — just stream through remaining chunks
            writer.writerows(first_chunk_rows)
            total_rows += len(first_chunk_rows)

            for _, batch in chunk_iter:
                writer.writerows(batch)
                total_rows += len(batch)

            audit_data = _build_audit(input_path, output_path, "csv", style,
                                      total_rows, headers, sensitive_cols, 0, pii_by_column, column_status)
            audit_path = get_audit_path(input_path, audit_base)
            save_audit_log(audit_data, audit_path)
            console.print(f"  [dim]Audit: {audit_path}[/dim]")

            console.print()
            console.print(Panel.fit(
                f"[green]✓ Scrubbing complete[/green]\n"
                f"  {total_rows} rows × {len(headers)} columns\n"
                f"  No PII detected — clean copy written\n"
                f"  Output: {output_path.name}",
                border_style="green",
            ))
            return {
                "total_rows": total_rows,
                "sensitive_columns": [],
                "total_cells_scrubbed": 0,
                "pii_by_column": {},
            }

        # Has sensitive columns — scrub in streaming mode
        pii_by_column = {h: 0 for h in sensitive_cols}
        pii_type_cache: dict[str, str] = {}

        # Process first chunk
        for row in first_chunk_rows:
            for header in sensitive_cols:
                value = str(row.get(header, ""))
                if not value.strip():
                    continue
                if value not in pii_type_cache:
                    pii_type_cache[value] = _get_pii_type_for_cell(value) or "generic"
                pii_type = pii_type_cache[value]
                row[header] = _generate_fake_value(value, pii_type)
                pii_by_column[header] += 1
                total_cells_scrubbed += 1

        writer.writerows(first_chunk_rows)
        total_rows += len(first_chunk_rows)

        # Stream remaining chunks from the same iterator
        for _, batch in chunk_iter:
            for row in batch:
                for header in sensitive_cols:
                    value = str(row.get(header, ""))
                    if not value.strip():
                        continue
                    if value not in pii_type_cache:
                        pii_type_cache[value] = _get_pii_type_for_cell(value) or "generic"
                    pii_type = pii_type_cache[value]
                    row[header] = _generate_fake_value(value, pii_type)
                    pii_by_column[header] += 1
                    total_cells_scrubbed += 1

            writer.writerows(batch)
            total_rows += len(batch)
            console.print(f"  [dim]  …{total_rows} rows processed[/dim]", end="\r")

        console.print(f"  [green]✓[/green] {total_rows} rows processed   ")
    finally:
        output_fh.close()

    # Display per-column stats
    for header in sensitive_cols:
        console.print(f"  [green]✓[/green] {header}: [yellow]{pii_by_column[header]}[/yellow] cells scrubbed")

    # --- Audit ---
    audit_data = _build_audit(input_path, output_path, "csv", style,
                              total_rows, headers, sensitive_cols, total_cells_scrubbed,
                              pii_by_column, column_status)
    audit_path = get_audit_path(input_path, audit_base)
    save_audit_log(audit_data, audit_path)
    console.print(f"  [dim]Audit: {audit_path}[/dim]")

    # --- Summary ---
    console.print()
    console.print(Panel.fit(
        f"[green]✓ Scrubbing complete[/green]\n"
        f"  {total_rows} rows × {len(headers)} columns\n"
        f"  {len(sensitive_cols)} sensitive columns found\n"
        f"  {total_cells_scrubbed} cells anonymized\n"
        f"  Output: {output_path.name}",
        border_style="green",
    ))

    return {
        "total_rows": total_rows,
        "sensitive_columns": sensitive_cols,
        "total_cells_scrubbed": total_cells_scrubbed,
        "pii_by_column": pii_by_column,
    }


def _build_audit(
    input_path, output_path, dump_format, style,
    total_rows, headers, sensitive_cols, total_cells_scrubbed,
    pii_by_column, column_status,
) -> dict:
    """Build audit log dict (shared between streaming and in-memory paths)."""
    return {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "input_file": str(input_path),
        "output_file": str(output_path),
        "format": dump_format,
        "style": style,
        "total_rows": total_rows,
        "total_columns": len(headers),
        "sensitive_columns": sensitive_cols,
        "total_cells_scrubbed": total_cells_scrubbed,
        "pii_by_column": pii_by_column,
        "column_classification": {h: ("SENSITIVE" if s else "clean") for h, s in column_status.items()},
    }


# ============================================================
#  SQL OUTPUT HELPER
# ============================================================

def _parse_sql_dump(filepath: Path) -> tuple[list[str], list[dict]]:
    """Parse a SQL dump file into structured rows.

    Handles common formats: INSERT INTO ... VALUES (...), (...);
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.split("\n")
    all_rows = []
    columns = []

    current_buffer = ""
    for line in lines:
        stripped = line.strip()

        # Skip comments and empty lines
        if not stripped or stripped.startswith("--") or stripped.startswith("#"):
            continue

        # Skip non-INSERT statements for now
        if not stripped.upper().startswith("INSERT"):
            continue

        # Accumulate multi-line INSERT statements
        current_buffer += " " + stripped
        if stripped.rstrip().endswith(";"):
            # Parse the complete INSERT
            parsed = _parse_sql_insert(current_buffer.strip())
            if parsed:
                if not columns:
                    columns = parsed["columns"]
                for row_vals in parsed["values"]:
                    if columns and len(columns) == len(row_vals):
                        all_rows.append(dict(zip(columns, row_vals)))
                    else:
                        # No column names: generate generic col_N names
                        gen_cols = [f"col_{i}" for i in range(len(row_vals))]
                        if not columns:
                            columns = gen_cols
                        all_rows.append(dict(zip(gen_cols, row_vals)))
            current_buffer = ""

    return columns, all_rows


def _write_sql_output(
    filepath: Path,
    rows: list[dict],
    headers: list[str],
    sensitive_cols: list[str],
    pii_by_column: dict,
):
    """Write scrubbed data back as SQL INSERT statements."""
    if not rows:
        return

    # Get table name from context (use 'scrubbed_data' as default)
    table_name = "scrubbed_data"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("-- DataCleaner Scrub-Dump Output\n")
        f.write(f"-- Generated at: {__import__('datetime').datetime.utcnow().isoformat()}Z\n")
        f.write(f"-- Sensitive columns scrubbed: {', '.join(sensitive_cols)}\n")
        f.write(f"-- Total cells anonymized: {sum(pii_by_column.values())}\n\n")

        # Write in batches of 50 rows
        batch_size = 50
        for batch_start in range(0, len(rows), batch_size):
            batch = rows[batch_start:batch_start + batch_size]
            col_list = ", ".join(f"`{h}`" for h in headers)

            values_parts = []
            for row in batch:
                vals = []
                for h in headers:
                    v = row.get(h, "")
                    if v is None or str(v).upper() == "NULL":
                        vals.append("NULL")
                    else:
                        # Escape single quotes
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")
                values_parts.append(f"({', '.join(vals)})")

            f.write(f"INSERT INTO `{table_name}` ({col_list}) VALUES\n")
            f.write(",\n".join(values_parts))
            f.write(";\n\n")

        f.write("-- End of scrubbed dump\n")
