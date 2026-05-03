"""Filesystem and encoding utilities for DataCleaner.

Provides safe file I/O with automatic encoding detection and fallback,
batch file operations, and filesystem helpers used across the scanner,
redactor, and audit pipeline.

All functions are designed for cross-platform compatibility (Windows/Linux/macOS)
and handle edge cases like BOM markers, mixed encodings, and large files.
"""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Iterator, Optional


# ============================================================
#  Encoding Detection & Safe I/O
# ============================================================

#: Common encodings to try, in order of likelihood for enterprise documents.
_FALLBACK_ENCODINGS: list[str] = [
    "utf-8",
    "utf-8-sig",  # UTF-8 with BOM
    "utf-16",
    "gbk",        # Chinese (GB2312 superset)
    "gb18030",    # Chinese (full Unicode)
    "latin-1",    # Western European (never fails — 1:1 byte mapping)
    "cp1252",     # Windows Western European
    "shift_jis",  # Japanese
    "euc-kr",     # Korean
]


def detect_encoding(
    filepath: str | Path,
    *,
    sample_size: int = 65536,
    default: str = "utf-8",
) -> str:
    """Detect the text encoding of a file using chardet (if available)
    with a fallback to heuristic sampling.

    Reads up to `sample_size` bytes from the beginning of the file
    for detection. For files smaller than sample_size, the entire
    file is read.

    Args:
        filepath: Path to the file.
        sample_size: Maximum bytes to read for detection (default: 64KB).
        default: Encoding to return if detection fails (default: utf-8).

    Returns:
        Encoding name string (e.g. 'utf-8', 'gbk', 'latin-1').

    Example:
        >>> import tempfile, os
        >>> with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
        ...     _ = f.write("hello".encode("utf-8"))
        ...     path = f.name
        >>> detect_encoding(path)
        'ascii'
        >>> os.unlink(path)
    """
    filepath = Path(filepath)

    try:
        file_size = filepath.stat().st_size
    except OSError:
        return default

    read_size = min(sample_size, file_size) if file_size > 0 else 0
    if read_size == 0:
        return default

    with open(filepath, "rb") as f:
        raw = f.read(read_size)

    # --- Attempt 1: chardet (most accurate) ---
    try:
        import chardet
        result = chardet.detect(raw)
        if result and result.get("encoding"):
            enc = result["encoding"]
            # Normalize common aliases
            if enc and "ascii" in enc.lower():
                return "utf-8"
            if enc and enc.lower() in ("gb2312", "gbk"):
                return "gbk"
            return enc
    except ImportError:
        pass

    # --- Attempt 2: BOM detection ---
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"

    # --- Attempt 3: heuristic — try utf-8 decode ---
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # --- Attempt 4: common encodings ---
    for enc in ["gbk", "utf-16", "latin-1"]:
        try:
            raw.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    return default


def read_text_safe(
    filepath: str | Path,
    *,
    encoding: str | None = None,
    fallback_encodings: list[str] | None = None,
) -> str:
    """Read a text file with automatic encoding fallback.

    Tries the specified encoding first, then falls back through a list
    of common encodings. If all fail, reads as latin-1 (which never fails
    — every byte maps to a character).

    Args:
        filepath: Path to the file.
        encoding: Preferred encoding. If None, auto-detects via detect_encoding().
        fallback_encodings: Encodings to try in order. Defaults to _FALLBACK_ENCODINGS.

    Returns:
        File contents as a string.

    Raises:
        FileNotFoundError: If the file doesn't exist.

    Example:
        >>> import tempfile, os
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        ...     _ = f.write("Café")
        ...     path = f.name
        >>> read_text_safe(path)
        'Café'
        >>> os.unlink(path)
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if encoding is None:
        encoding = detect_encoding(filepath)

    encodings_to_try = [encoding] + (fallback_encodings or _FALLBACK_ENCODINGS)

    # Deduplicate while preserving order
    seen: set[str] = set()
    for enc in encodings_to_try:
        if enc in seen:
            continue
        seen.add(enc)
        try:
            return filepath.read_text(encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # Absolute last resort: latin-1 maps every byte 1:1 (never fails)
    return filepath.read_text(encoding="latin-1")


def write_text_safe(
    filepath: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
    make_dirs: bool = True,
) -> Path:
    """Write text content to a file, creating parent directories as needed.

    Args:
        filepath: Destination path.
        content: Text content to write.
        encoding: Output encoding (default: utf-8).
        make_dirs: If True, create parent directories if they don't exist.

    Returns:
        The Path object of the written file.

    Example:
        >>> import tempfile, os
        >>> dir_ = tempfile.mkdtemp()
        >>> path = os.path.join(dir_, "sub", "test.txt")
        >>> write_text_safe(path, "hello")
        PosixPath('.../sub/test.txt')
        >>> read_text_safe(path)
        'hello'
    """
    filepath = Path(filepath)

    if make_dirs:
        filepath.parent.mkdir(parents=True, exist_ok=True)

    filepath.write_text(content, encoding=encoding)
    return filepath


# ============================================================
#  File Search & Discovery
# ============================================================

def find_files(
    directory: str | Path,
    *,
    pattern: str = "*",
    recursive: bool = True,
    max_depth: int | None = None,
    exclude_patterns: list[str] | None = None,
    min_size: int = 0,
    max_size: int | None = None,
) -> list[Path]:
    """Find files matching criteria in a directory tree.

    Args:
        directory: Root directory to search.
        pattern: Glob pattern for filename matching (e.g. '*.csv', 'report_*').
        recursive: If True, search subdirectories (default: True).
        max_depth: Maximum directory depth (None = unlimited).
        exclude_patterns: Glob patterns to exclude (e.g. ['*.tmp', '.*']).
        min_size: Minimum file size in bytes (default: 0).
        max_size: Maximum file size in bytes (None = unlimited).

    Returns:
        Sorted list of matching file paths.

    Example:
        >>> import tempfile, os
        >>> dir_ = tempfile.mkdtemp()
        >>> (Path(dir_) / "a.csv").write_text("x")
        >>> (Path(dir_) / "b.txt").write_text("y")
        >>> result = find_files(dir_, pattern="*.csv")
        >>> len(result) == 1
        True
        >>> result[0].name
        'a.csv'
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    exclude_patterns = exclude_patterns or []
    results: list[Path] = []

    glob_method = directory.rglob if recursive else directory.glob

    for filepath in glob_method(pattern):
        if not filepath.is_file():
            continue

        # Depth check
        if max_depth is not None:
            relative_depth = len(filepath.relative_to(directory).parts) - 1
            if relative_depth > max_depth:
                continue

        # Exclude pattern check
        if any(filepath.match(ep) for ep in exclude_patterns):
            continue

        # Size check
        try:
            size = filepath.stat().st_size
        except OSError:
            continue

        if size < min_size:
            continue
        if max_size is not None and size > max_size:
            continue

        results.append(filepath)

    return sorted(results)


# ============================================================
#  File Information
# ============================================================

def get_file_size_display(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string.

    Uses binary prefixes (KiB, MiB, GiB) for sizes >= 1024 bytes.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Human-readable string (e.g. '1.5 MiB', '512 B').

    Example:
        >>> get_file_size_display(0)
        '0 B'
        >>> get_file_size_display(1536)
        '1.50 KiB'
        >>> get_file_size_display(1048576)
        '1.00 MiB'
    """
    if size_bytes < 0:
        raise ValueError("size_bytes must be non-negative")

    if size_bytes < 1024:
        return f"{size_bytes} B"

    for unit in ("KiB", "MiB", "GiB", "TiB"):
        size_bytes /= 1024.0
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"

    return f"{size_bytes:.2f} PiB"


def compute_file_hash(
    filepath: str | Path,
    *,
    algorithm: str = "sha256",
    chunk_size: int = 65536,
) -> str:
    """Compute a cryptographic hash of a file.

    Used for integrity verification of scanned documents and audit logs.

    Args:
        filepath: Path to the file.
        algorithm: Hash algorithm (sha256, sha512, md5, etc.). Default: sha256.
        chunk_size: Read buffer size in bytes.

    Returns:
        Hex-encoded hash digest string.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the algorithm is not supported by hashlib.

    Example:
        >>> import tempfile, os
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        ...     _ = f.write("hello world")
        ...     path = f.name
        >>> h = compute_file_hash(path, algorithm="md5")
        >>> len(h) == 32  # MD5 produces 32 hex chars
        True
        >>> os.unlink(path)
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


def split_filepath(filepath: str | Path) -> dict[str, str]:
    """Decompose a file path into its components.

    Args:
        filepath: Any file path string or Path object.

    Returns:
        Dict with keys: 'full_path', 'directory', 'filename', 'stem',
        'extension', 'parent_dir_name'.

    Example:
        >>> split_filepath("/home/user/docs/report.pdf")
        {'full_path': '/home/user/docs/report.pdf', 'directory': '/home/user/docs', 'filename': 'report.pdf', 'stem': 'report', 'extension': '.pdf', 'parent_dir_name': 'docs'}
    """
    p = Path(filepath)
    return {
        "full_path": str(p),
        "directory": str(p.parent),
        "filename": p.name,
        "stem": p.stem,
        "extension": p.suffix,
        "parent_dir_name": p.parent.name if p.parent != p.parent.parent else "",
    }


# ============================================================
#  Filesystem Operations
# ============================================================

def ensure_dir(path: str | Path) -> Path:
    """Create a directory and all parents if they don't exist.

    Idempotent — safe to call multiple times. Similar to mkdir -p.

    Args:
        path: Directory path to ensure exists.

    Returns:
        Path object of the directory.

    Example:
        >>> import tempfile
        >>> dir_ = tempfile.mkdtemp()
        >>> new_dir = os.path.join(dir_, "a", "b", "c")
        >>> p = ensure_dir(new_dir)
        >>> p.is_dir()
        True
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write(
    filepath: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Write content to a file atomically via a temporary file + rename.

    Prevents partial writes: if the write fails, the original file is intact.
    Uses os.replace() which is atomic on POSIX and (mostly) on Windows.

    Args:
        filepath: Target path.
        content: Text content.
        encoding: Encoding for the file.

    Returns:
        Path to the written file.

    Example:
        >>> import tempfile, os
        >>> dir_ = tempfile.mkdtemp()
        >>> path = os.path.join(dir_, "config.yaml")
        >>> atomic_write(path, "key: value")
        PosixPath('.../config.yaml')
        >>> read_text_safe(path)
        'key: value'
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file in the same directory (same filesystem = atomic rename)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(filepath.parent),
        prefix=f".{filepath.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
        os.replace(tmp_path, filepath)  # Atomic on same filesystem
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return filepath


def batch_rename(
    directory: str | Path,
    mapping: dict[str, str],
    *,
    dry_run: bool = False,
) -> list[tuple[str, str, bool]]:
    """Rename multiple files in a directory according to a mapping.

    Each key in the mapping is a source filename (relative to directory),
    each value is the destination filename. Only renames files within the
    same directory — no cross-directory moves.

    Args:
        directory: Directory containing the files.
        mapping: Dict of {old_name: new_name}.
        dry_run: If True, return planned renames without executing.

    Returns:
        List of (old_name, new_name, success) tuples.

    Example:
        >>> import tempfile, os
        >>> dir_ = tempfile.mkdtemp()
        >>> (Path(dir_) / "old.txt").write_text("data")
        >>> results = batch_rename(dir_, {"old.txt": "new.txt"})
        >>> results[0][2]  # success flag
        True
        >>> (Path(dir_) / "new.txt").exists()
        True
    """
    directory = Path(directory)
    results: list[tuple[str, str, bool]] = []

    for old_name, new_name in mapping.items():
        old_path = directory / old_name
        new_path = directory / new_name

        if dry_run:
            exists = old_path.exists()
            results.append((old_name, new_name, exists))
            continue

        try:
            if not old_path.exists():
                results.append((old_name, new_name, False))
                continue

            if new_path.exists():
                results.append((old_name, new_name, False))
                continue

            old_path.rename(new_path)
            results.append((old_name, new_name, True))
        except OSError:
            results.append((old_name, new_name, False))

    return results
