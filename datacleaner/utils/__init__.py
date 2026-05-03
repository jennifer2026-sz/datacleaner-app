"""DataCleaner utility modules.

Converters
    Format conversion between CSV, JSON, YAML, and Python data structures.
    Designed for pre/post-processing of scanned documents.

File Utils
    Encoding detection, safe file I/O with fallback, batch file operations,
    and filesystem helpers.
"""

from datacleaner.utils.converters import (
    csv_to_json,
    csv_to_dicts,
    csv_to_yaml,
    dicts_to_csv,
    dicts_to_json,
    json_to_csv,
    json_to_dicts,
    json_to_yaml,
    yaml_to_dicts,
    yaml_to_json,
    detect_format,
    normalize_row,
)
from datacleaner.utils.file_utils import (
    detect_encoding,
    read_text_safe,
    write_text_safe,
    find_files,
    get_file_size_display,
    compute_file_hash,
    split_filepath,
    ensure_dir,
    atomic_write,
    batch_rename,
)

__all__ = [
    # Converters
    "csv_to_json",
    "csv_to_dicts",
    "csv_to_yaml",
    "dicts_to_csv",
    "dicts_to_json",
    "json_to_csv",
    "json_to_dicts",
    "json_to_yaml",
    "yaml_to_dicts",
    "yaml_to_json",
    "detect_format",
    "normalize_row",
    # File Utils
    "detect_encoding",
    "read_text_safe",
    "write_text_safe",
    "find_files",
    "get_file_size_display",
    "compute_file_hash",
    "split_filepath",
    "ensure_dir",
    "atomic_write",
    "batch_rename",
]
