"""Data format conversion utilities.

Provides lossless round-trip conversion between common data serialization formats
used in PII scanning workflows: CSV, JSON, YAML, and Python dicts/lists.

All functions are idempotent and encoding-safe. Designed for use in pre-processing
(raw data → structured) and post-processing (scan results → export).

Examples:
    >>> from datacleaner.utils import csv_to_json, dicts_to_csv
    >>> json_str = csv_to_json("data.csv")
    >>> csv_str = dicts_to_csv([{"name": "Alice", "email": "a@b.com"}])
"""

import csv
import io
import json
import os
from pathlib import Path
from typing import Any


# ============================================================
#  CSV ↔ Python data structures
# ============================================================

def csv_to_dicts(
    source: str | Path | io.StringIO,
    *,
    delimiter: str = ",",
    encoding: str = "utf-8",
    skip_empty: bool = True,
) -> list[dict[str, str]]:
    """Parse CSV data into a list of dictionaries.

    Column headers are taken from the first row. Each subsequent row becomes
    a dict mapping header → value. Empty rows are skipped by default.

    Args:
        source: File path, Path object, or StringIO buffer containing CSV data.
        delimiter: Field delimiter (default: comma).
        encoding: File encoding when source is a path (default: utf-8).
        skip_empty: If True, skip rows where all values are empty strings.

    Returns:
        List of dicts, one per data row. Keys are the header row values.

    Raises:
        FileNotFoundError: If source is a path and the file doesn't exist.
        ValueError: If the CSV is malformed (e.g. inconsistent column count).

    Example:
        >>> csv_to_dicts("name,email\\nAlice,a@b.com\\nBob,b@c.com")
        [{'name': 'Alice', 'email': 'a@b.com'}, {'name': 'Bob', 'email': 'b@c.com'}]
    """
    if isinstance(source, (str, Path)):
        with open(source, "r", encoding=encoding, newline="") as f:
            return _parse_csv_reader(csv.DictReader(f, delimiter=delimiter), skip_empty)
    elif isinstance(source, io.StringIO):
        return _parse_csv_reader(csv.DictReader(source, delimiter=delimiter), skip_empty)
    else:
        raise TypeError(f"source must be str, Path, or StringIO, got {type(source).__name__}")


def _parse_csv_reader(
    reader: csv.DictReader,
    skip_empty: bool,
) -> list[dict[str, str]]:
    """Internal: extract rows from a csv.DictReader, optionally filtering empty rows."""
    rows = []
    for row in reader:
        if skip_empty and all(v.strip() == "" for v in row.values()):
            continue
        rows.append(dict(row))
    return rows


def dicts_to_csv(
    data: list[dict[str, Any]],
    *,
    delimiter: str = ",",
    include_header: bool = True,
) -> str:
    """Serialize a list of dictionaries to a CSV string.

    Column order is determined by the keys of the first dict. All values are
    stringified via str(). If include_header is False, only data rows are output.

    Args:
        data: List of dicts to serialize. All dicts should share the same keys.
        delimiter: Field delimiter (default: comma).
        include_header: If True, write a header row with dict keys.

    Returns:
        CSV-formatted string with platform-native line endings.

    Raises:
        ValueError: If data is empty or dicts have inconsistent keys.

    Example:
        >>> dicts_to_csv([{"name": "Alice", "score": 95}])
        'name,score\\r\\nAlice,95\\r\\n'
    """
    if not data:
        raise ValueError("data must not be empty")

    # Collect all keys, preserving order from first dict
    fieldnames = list(data[0].keys())

    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=delimiter,
        extrasaction="ignore",
    )

    if include_header:
        writer.writeheader()

    for row in data:
        # Stringify all values for safe CSV output
        safe_row = {k: str(v) for k, v in row.items() if k in fieldnames}
        writer.writerow(safe_row)

    return output.getvalue()


# ============================================================
#  CSV → JSON / JSON → CSV
# ============================================================

def csv_to_json(
    source: str | Path,
    *,
    delimiter: str = ",",
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
) -> str:
    """Convert a CSV file to a JSON string.

    Each CSV row becomes a JSON object. The entire file becomes a JSON array.

    Args:
        source: Path to the CSV file.
        delimiter: CSV field delimiter.
        encoding: File encoding.
        indent: JSON indentation level (0 for compact).
        ensure_ascii: If True, escape non-ASCII characters (default: False).

    Returns:
        JSON string representation of the CSV data.

    Example:
        >>> import tempfile, os
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        ...     _ = f.write("name,score\\nAlice,95")
        ...     path = f.name
        >>> result = csv_to_json(path)
        >>> '"name": "Alice"' in result
        True
        >>> os.unlink(path)
    """
    rows = csv_to_dicts(source, delimiter=delimiter, encoding=encoding)
    return json.dumps(rows, indent=indent, ensure_ascii=ensure_ascii) if indent else json.dumps(rows, ensure_ascii=ensure_ascii, separators=(",", ":"))


def json_to_csv(
    source: str | Path | list[dict],
    *,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> str:
    """Convert JSON data (file or list of dicts) to CSV string.

    Accepts either a file path to a JSON file, or an already-parsed list of dicts.
    The JSON must be an array of objects with consistent keys.

    Args:
        source: Path to a JSON file, or a list of dicts.
        delimiter: CSV field delimiter.
        encoding: File encoding (ignored when source is a list).

    Returns:
        CSV string.

    Raises:
        FileNotFoundError: If the JSON file doesn't exist.
        ValueError: If the JSON structure is not an array of objects.

    Example:
        >>> json_to_csv([{"a": 1, "b": 2}])
        'a,b\\r\\n1,2\\r\\n'
    """
    if isinstance(source, list):
        return dicts_to_csv(source, delimiter=delimiter)
    else:
        rows = json_to_dicts(source, encoding=encoding)
        return dicts_to_csv(rows, delimiter=delimiter)


# ============================================================
#  JSON ↔ Python data structures
# ============================================================

def json_to_dicts(
    source: str | Path,
    *,
    encoding: str = "utf-8",
) -> list[dict]:
    """Load a JSON file and return as a list of dicts.

    The root JSON value must be an array of objects. Single-object files
    will be wrapped in a list automatically for convenience.

    Args:
        source: Path to the JSON file.
        encoding: File encoding.

    Returns:
        List of dicts parsed from the JSON content.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the JSON root is a scalar or malformed.

    Example:
        >>> import json, tempfile, os
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        ...     _ = json.dump([{"k": "v"}], f)
        ...     path = f.name
        >>> json_to_dicts(path)
        [{'k': 'v'}]
        >>> os.unlink(path)
    """
    with open(source, "r", encoding=encoding) as f:
        data = json.load(f)

    if isinstance(data, dict):
        # Convenience: wrap single object in a list
        return [data]
    elif isinstance(data, list):
        if not all(isinstance(item, dict) for item in data):
            raise ValueError("JSON array must contain only objects")
        return data
    else:
        raise ValueError(
            f"JSON root must be an object or array of objects, got {type(data).__name__}"
        )


def dicts_to_json(
    data: list[dict],
    *,
    indent: int = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
) -> str:
    """Serialize a list of dicts to a JSON string.

    Args:
        data: List of dicts to serialize.
        indent: JSON indentation (0 for compact/minified).
        ensure_ascii: If True, escape non-ASCII (default: False — preserves Unicode).
        sort_keys: If True, sort object keys alphabetically.

    Returns:
        JSON string.

    Example:
        >>> dicts_to_json([{"a": 1}])
        '[\\n  {\\n    "a": 1\\n  }\\n]'
    """
    return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys) if indent else json.dumps(data, ensure_ascii=ensure_ascii, sort_keys=sort_keys, separators=(",", ":"))


# ============================================================
#  YAML ↔ JSON / Python
# ============================================================

def yaml_to_dicts(
    source: str | Path,
    *,
    encoding: str = "utf-8",
) -> list[dict]:
    """Load a YAML file and return as a list of dicts.

    Supports both a top-level list and a top-level mapping (wrapped in a list).

    Args:
        source: Path to the YAML file.
        encoding: File encoding.

    Returns:
        List of dicts.

    Raises:
        ImportError: If PyYAML is not installed.
        FileNotFoundError: If the file doesn't exist.
    """
    import yaml

    with open(source, "r", encoding=encoding) as f:
        data = yaml.safe_load(f)

    if data is None:
        return []
    elif isinstance(data, list):
        return data
    elif isinstance(data, dict):
        return [data]
    else:
        raise ValueError(f"Unexpected YAML root type: {type(data).__name__}")


def json_to_yaml(
    source: str | Path,
    *,
    encoding: str = "utf-8",
) -> str:
    """Convert a JSON file to a YAML string.

    Args:
        source: Path to the JSON file.
        encoding: File encoding.

    Returns:
        YAML string.

    Raises:
        ImportError: If PyYAML is not installed.
    """
    import yaml
    data = json_to_dicts(source, encoding=encoding)
    return yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)


def yaml_to_json(
    source: str | Path,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
) -> str:
    """Convert a YAML file to a JSON string.

    Args:
        source: Path to the YAML file.
        encoding: File encoding.
        indent: JSON indentation.

    Returns:
        JSON string.
    """
    data = yaml_to_dicts(source, encoding=encoding)
    return dicts_to_json(data, indent=indent)


def csv_to_yaml(
    source: str | Path,
    *,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> str:
    """Convert a CSV file to a YAML string.

    Args:
        source: Path to the CSV file.
        delimiter: CSV field delimiter.
        encoding: File encoding.

    Returns:
        YAML string.

    Raises:
        ImportError: If PyYAML is not installed.
    """
    import yaml

    rows = csv_to_dicts(source, delimiter=delimiter, encoding=encoding)
    return yaml.dump(rows, allow_unicode=True, sort_keys=False, default_flow_style=False)


# ============================================================
#  Format Detection
# ============================================================

#: Mapping of lowercase file extensions to format names.
_FORMAT_MAP: dict[str, str] = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
    ".xml": "xml",
    ".txt": "text",
    ".md": "text",
    ".log": "text",
}


def detect_format(filepath: str | Path) -> str | None:
    """Detect the data format of a file based on its extension.

    Args:
        filepath: Path to the file.

    Returns:
        Format name string (e.g. 'csv', 'json', 'yaml'), or None if unrecognized.

    Example:
        >>> detect_format("data.csv")
        'csv'
        >>> detect_format("report.json")
        'json'
        >>> detect_format("image.png") is None
        True
    """
    suffix = Path(filepath).suffix.lower()
    return _FORMAT_MAP.get(suffix)


# ============================================================
#  Utility Helpers
# ============================================================

def normalize_row(
    row: dict[str, Any],
    *,
    strip: bool = True,
    lowercase_keys: bool = False,
) -> dict[str, Any]:
    """Normalize a single data row for consistent processing.

    - Strips whitespace from string values (optional, default: True).
    - Optionally lowercases all keys for case-insensitive matching.
    - Converts common string representations to Python types:
      "true"/"false" → bool, "123" → int, "1.5" → float, "" / "null" / "none" → None.

    Args:
        row: Dict representing one data row.
        strip: If True, strip leading/trailing whitespace from string values.
        lowercase_keys: If True, convert all keys to lowercase.

    Returns:
        A new dict with normalized values. The original dict is not modified.

    Example:
        >>> normalize_row({" Name ": " Alice ", "active": "true"})
        {' Name ': 'Alice', 'active': True}
        >>> normalize_row({"Name": "Alice"}, lowercase_keys=True)
        {'name': 'Alice'}
    """
    normalized: dict[str, Any] = {}

    for key, value in row.items():
        new_key = key.lower() if lowercase_keys else key

        if isinstance(value, str):
            if strip:
                value = value.strip()
            # Only coerce stripped values; unstripped numeric-looking strings stay as-is
            if strip or value == value.strip():
                normalized[new_key] = _coerce_value(value)
            else:
                normalized[new_key] = value
        else:
            normalized[new_key] = value

    return normalized


def _coerce_value(value: str) -> Any:
    """Coerce a string to its likely intended Python type.

    Handles: booleans, integers, floats, null sentinels.
    If the string has leading/trailing whitespace, it is NOT coerced
    to a number (preserving data fidelity for unstripped values).
    If no coercion applies, returns the original string.
    """
    if not value:
        return None

    lower = value.lower()

    # Null sentinels
    if lower in ("null", "none", "nil", "na", "n/a"):
        return None

    # Booleans
    if lower == "true":
        return True
    if lower == "false":
        return False

    # If the value has leading/trailing whitespace, don't coerce numbers
    # (caller should strip first; unstripped values stay as-is)
    stripped = value.strip()

    # Integers (no decimal point, no scientific notation)
    if stripped.lstrip("-").isdigit():
        try:
            return int(stripped)
        except ValueError:
            pass

    # Floats
    try:
        return float(stripped)
    except ValueError:
        pass

    return value
