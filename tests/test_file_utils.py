"""Tests for datacleaner.utils.file_utils — filesystem and encoding utilities.

Covers: encoding detection, safe file I/O, file search/discovery,
file size formatting, hash computation, path decomposition,
atomic writes, and batch rename.
"""

import os
import tempfile
from pathlib import Path

import pytest


# ============================================================
#  Test Fixtures
# ============================================================

@pytest.fixture
def temp_utf8_file(tmp_path):
    """Create a UTF-8 file with non-ASCII content."""
    path = tmp_path / "utf8.txt"
    path.write_text("Café résumé naïve", encoding="utf-8")
    return str(path)


@pytest.fixture
def temp_gbk_file(tmp_path):
    """Create a GBK-encoded Chinese text file."""
    path = tmp_path / "gbk.txt"
    try:
        path.write_text("你好世界", encoding="gbk")
        return str(path)
    except LookupError:
        # GBK codec not available in this environment
        # Create a fallback file that will test the encoding fallback logic
        path.write_text("hello world", encoding="utf-8")
        return str(path)


@pytest.fixture
def temp_utf16_file(tmp_path):
    """Create a UTF-16 file."""
    path = tmp_path / "utf16.txt"
    path.write_text("Hello UTF-16", encoding="utf-16")
    return str(path)


@pytest.fixture
def temp_file_tree(tmp_path):
    """Create a directory tree for file search tests."""
    base = tmp_path / "search_test"
    base.mkdir()

    (base / "a.csv").write_text("csv1")
    (base / "b.csv").write_text("csv2")
    (base / "notes.txt").write_text("text")

    sub = base / "subdir"
    sub.mkdir()
    (sub / "deep.csv").write_text("deep")
    (sub / ".hidden").write_text("hidden")

    empty_sub = base / "empty_dir"
    empty_sub.mkdir()

    return str(base)


@pytest.fixture
def large_temp_file(tmp_path):
    """Create a file >1KB for size formatting tests."""
    path = tmp_path / "medium.bin"
    path.write_bytes(b"x" * 2048)  # 2 KiB
    return str(path)


# ============================================================
#  detect_encoding
# ============================================================

class TestDetectEncoding:
    """Tests for detect_encoding."""

    def test_utf8(self, temp_utf8_file):
        from datacleaner.utils.file_utils import detect_encoding

        enc = detect_encoding(temp_utf8_file)
        assert enc in ("utf-8", "ascii")  # ASCII subset of UTF-8

    def test_utf16(self, temp_utf16_file):
        from datacleaner.utils.file_utils import detect_encoding

        enc = detect_encoding(temp_utf16_file)
        # UTF-16 should be detected (not utf-8)
        assert "utf" in enc.lower()

    def test_gbk(self, temp_gbk_file):
        from datacleaner.utils.file_utils import detect_encoding

        enc = detect_encoding(temp_gbk_file)
        # Should return some encoding (not fail)
        assert isinstance(enc, str)
        assert len(enc) > 0

    def test_empty_file(self, tmp_path):
        from datacleaner.utils.file_utils import detect_encoding

        path = tmp_path / "empty.txt"
        path.write_text("", encoding="utf-8")
        enc = detect_encoding(str(path))
        assert enc == "utf-8"  # Default for empty files

    def test_nonexistent_file(self, tmp_path):
        from datacleaner.utils.file_utils import detect_encoding

        enc = detect_encoding(str(tmp_path / "nope.txt"))
        assert enc == "utf-8"  # Returns default on error

    def test_custom_default(self, temp_utf8_file):
        from datacleaner.utils.file_utils import detect_encoding

        enc = detect_encoding(temp_utf8_file, default="latin-1")
        assert enc in ("utf-8", "ascii")  # Should detect actual encoding, not use default


# ============================================================
#  read_text_safe
# ============================================================

class TestReadTextSafe:
    """Tests for read_text_safe."""

    def test_read_utf8(self, temp_utf8_file):
        from datacleaner.utils.file_utils import read_text_safe

        content = read_text_safe(temp_utf8_file)
        assert "Café" in content

    def test_read_with_explicit_encoding(self, temp_gbk_file):
        from datacleaner.utils.file_utils import read_text_safe

        try:
            content = read_text_safe(temp_gbk_file, encoding="gbk")
            assert len(content) > 0
        except LookupError:
            pytest.skip("GBK codec not available")

    def test_fallback_encoding(self, tmp_path):
        """Verify fallback works when primary encoding fails."""
        from datacleaner.utils.file_utils import read_text_safe

        path = tmp_path / "test.txt"
        path.write_text("hello", encoding="utf-8")

        # Specify wrong primary encoding, should fall back
        content = read_text_safe(
            str(path),
            encoding="utf-16",  # Wrong — will fall back
            fallback_encodings=["utf-8"],
        )
        assert content == "hello"

    def test_file_not_found(self):
        from datacleaner.utils.file_utils import read_text_safe

        with pytest.raises(FileNotFoundError):
            read_text_safe("/nonexistent/file.txt")

    def test_latin1_fallback_never_fails(self, tmp_path):
        """Latin-1 maps every byte 1:1 — should never raise."""
        from datacleaner.utils.file_utils import read_text_safe

        path = tmp_path / "binary.bin"
        path.write_bytes(bytes(range(256)))

        # Should not raise — latin-1 is the ultimate fallback
        content = read_text_safe(str(path))
        assert len(content) == 256


# ============================================================
#  write_text_safe
# ============================================================

class TestWriteTextSafe:
    """Tests for write_text_safe."""

    def test_basic_write(self, tmp_path):
        from datacleaner.utils.file_utils import write_text_safe, read_text_safe

        path = str(tmp_path / "output.txt")
        result = write_text_safe(path, "Hello World")
        assert result.exists()
        assert read_text_safe(path) == "Hello World"

    def test_creates_parent_dirs(self, tmp_path):
        from datacleaner.utils.file_utils import write_text_safe

        deep_path = str(tmp_path / "a" / "b" / "c" / "deep.txt")
        p = write_text_safe(deep_path, "deep content")
        assert p.exists()
        assert p.read_text() == "deep content"

    def test_no_make_dirs_raises(self, tmp_path):
        from datacleaner.utils.file_utils import write_text_safe

        path = str(tmp_path / "nonexistent_dir" / "file.txt")
        with pytest.raises(FileNotFoundError):
            write_text_safe(path, "content", make_dirs=False)

    def test_unicode_content(self, tmp_path):
        from datacleaner.utils.file_utils import write_text_safe, read_text_safe

        path = str(tmp_path / "unicode.txt")
        write_text_safe(path, "中文 español العربية")
        assert "中文" in read_text_safe(path)

    def test_overwrite_existing(self, tmp_path):
        from datacleaner.utils.file_utils import write_text_safe

        path = str(tmp_path / "overwrite.txt")
        write_text_safe(path, "old")
        write_text_safe(path, "new")
        assert Path(path).read_text() == "new"


# ============================================================
#  find_files
# ============================================================

class TestFindFiles:
    """Tests for find_files — recursive file search."""

    def test_find_by_pattern(self, temp_file_tree):
        from datacleaner.utils.file_utils import find_files

        results = find_files(temp_file_tree, pattern="*.csv")
        names = [p.name for p in results]
        assert len(names) == 3  # a.csv, b.csv, deep.csv
        assert "a.csv" in names
        assert "deep.csv" in names

    def test_non_recursive(self, temp_file_tree):
        from datacleaner.utils.file_utils import find_files

        results = find_files(temp_file_tree, pattern="*.csv", recursive=False)
        names = [p.name for p in results]
        assert "a.csv" in names
        assert "deep.csv" not in names  # In subdir

    def test_max_depth(self, temp_file_tree):
        from datacleaner.utils.file_utils import find_files

        results = find_files(temp_file_tree, pattern="*.csv", max_depth=0)
        names = [p.name for p in results]
        assert len(names) == 2  # a.csv, b.csv (root level only)
        assert "deep.csv" not in names

    def test_exclude_patterns(self, temp_file_tree):
        from datacleaner.utils.file_utils import find_files

        results = find_files(temp_file_tree, pattern="*", exclude_patterns=["*.csv"])
        names = [p.name for p in results]
        assert "notes.txt" in names
        assert "a.csv" not in names

    def test_exclude_hidden(self, temp_file_tree):
        from datacleaner.utils.file_utils import find_files

        results = find_files(temp_file_tree, pattern="*", exclude_patterns=[".*"])
        names = [p.name for p in results]
        assert ".hidden" not in names

    def test_min_size(self, temp_file_tree):
        from datacleaner.utils.file_utils import find_files

        results = find_files(temp_file_tree, pattern="*", min_size=100)
        # All test files are small (<100 bytes)
        assert len(results) == 0

    def test_max_size(self, temp_file_tree):
        from datacleaner.utils.file_utils import find_files

        results = find_files(temp_file_tree, pattern="*", max_size=10)
        names = [p.name for p in results]
        # csv files are 4 bytes each, should pass; any >10 byte file excluded
        assert "a.csv" in names

    def test_not_a_directory_raises(self, tmp_path):
        from datacleaner.utils.file_utils import find_files

        path = tmp_path / "file.txt"
        path.write_text("not a dir")
        with pytest.raises(NotADirectoryError):
            find_files(str(path))

    def test_empty_directory(self, tmp_path):
        from datacleaner.utils.file_utils import find_files

        empty = tmp_path / "empty"
        empty.mkdir()
        results = find_files(str(empty))
        assert results == []


# ============================================================
#  get_file_size_display
# ============================================================

class TestGetFileSizeDisplay:
    """Tests for get_file_size_display."""

    def test_bytes_range(self):
        from datacleaner.utils.file_utils import get_file_size_display

        assert get_file_size_display(0) == "0 B"
        assert get_file_size_display(1) == "1 B"
        assert get_file_size_display(1023) == "1023 B"

    def test_kib_range(self):
        from datacleaner.utils.file_utils import get_file_size_display

        assert get_file_size_display(1024) == "1.00 KiB"
        assert get_file_size_display(1536) == "1.50 KiB"

    def test_mib_range(self):
        from datacleaner.utils.file_utils import get_file_size_display

        assert get_file_size_display(1048576) == "1.00 MiB"

    def test_gib_range(self):
        from datacleaner.utils.file_utils import get_file_size_display

        assert get_file_size_display(1073741824) == "1.00 GiB"

    def test_negative_raises(self):
        from datacleaner.utils.file_utils import get_file_size_display

        with pytest.raises(ValueError, match="non-negative"):
            get_file_size_display(-1)

    def test_large_temp_file(self, large_temp_file):
        from datacleaner.utils.file_utils import get_file_size_display

        size = Path(large_temp_file).stat().st_size
        display = get_file_size_display(size)
        assert "KiB" in display


# ============================================================
#  compute_file_hash
# ============================================================

class TestComputeFileHash:
    """Tests for compute_file_hash."""

    def test_sha256(self, tmp_path):
        from datacleaner.utils.file_utils import compute_file_hash

        path = tmp_path / "hashme.txt"
        path.write_text("hello world", encoding="utf-8")

        h = compute_file_hash(str(path))
        assert len(h) == 64  # SHA-256 = 64 hex chars
        # Known SHA-256 of "hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert h == expected

    def test_md5(self, tmp_path):
        from datacleaner.utils.file_utils import compute_file_hash

        path = tmp_path / "hashme.txt"
        path.write_text("hello world", encoding="utf-8")

        h = compute_file_hash(str(path), algorithm="md5")
        assert len(h) == 32  # MD5 = 32 hex chars
        # Known MD5 of "hello world"
        assert h == "5eb63bbbe01eeed093cb22bb8f5acdc3"

    def test_sha512(self, tmp_path):
        from datacleaner.utils.file_utils import compute_file_hash

        path = tmp_path / "hashme.txt"
        path.write_text("test", encoding="utf-8")

        h = compute_file_hash(str(path), algorithm="sha512")
        assert len(h) == 128  # SHA-512 = 128 hex chars

    def test_deterministic(self, tmp_path):
        from datacleaner.utils.file_utils import compute_file_hash

        path = tmp_path / "same.txt"
        path.write_text("same content", encoding="utf-8")

        h1 = compute_file_hash(str(path))
        h2 = compute_file_hash(str(path))
        assert h1 == h2

    def test_different_content(self, tmp_path):
        from datacleaner.utils.file_utils import compute_file_hash

        p1 = tmp_path / "a.txt"
        p1.write_text("alpha")
        p2 = tmp_path / "b.txt"
        p2.write_text("beta")

        assert compute_file_hash(str(p1)) != compute_file_hash(str(p2))

    def test_file_not_found(self):
        from datacleaner.utils.file_utils import compute_file_hash

        with pytest.raises(FileNotFoundError):
            compute_file_hash("/no/such/file.txt")

    def test_invalid_algorithm(self, tmp_path):
        from datacleaner.utils.file_utils import compute_file_hash

        path = tmp_path / "file.txt"
        path.write_text("test")
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            compute_file_hash(str(path), algorithm="sha-999")


# ============================================================
#  split_filepath
# ============================================================

class TestSplitFilepath:
    """Tests for split_filepath."""

    def test_full_decomposition(self):
        from datacleaner.utils.file_utils import split_filepath

        result = split_filepath("/home/user/docs/report.pdf")
        assert result["full_path"] == "/home/user/docs/report.pdf"
        assert result["directory"] == "/home/user/docs"
        assert result["filename"] == "report.pdf"
        assert result["stem"] == "report"
        assert result["extension"] == ".pdf"
        assert result["parent_dir_name"] == "docs"

    def test_no_extension(self):
        from datacleaner.utils.file_utils import split_filepath

        result = split_filepath("/usr/bin/script")
        assert result["stem"] == "script"
        assert result["extension"] == ""

    def test_multiple_extensions(self):
        from datacleaner.utils.file_utils import split_filepath

        result = split_filepath("archive.tar.gz")
        assert result["stem"] == "archive.tar"
        assert result["extension"] == ".gz"

    def test_hidden_file(self):
        from datacleaner.utils.file_utils import split_filepath

        result = split_filepath("/home/.bashrc")
        assert result["filename"] == ".bashrc"
        assert result["stem"] == ".bashrc"

    def test_root_directory(self):
        from datacleaner.utils.file_utils import split_filepath

        result = split_filepath("/root_file.txt")
        assert result["directory"] == "/"
        assert result["parent_dir_name"] == ""


# ============================================================
#  ensure_dir
# ============================================================

class TestEnsureDir:
    """Tests for ensure_dir."""

    def test_creates_nested(self, tmp_path):
        from datacleaner.utils.file_utils import ensure_dir

        path = tmp_path / "a" / "b" / "c"
        result = ensure_dir(str(path))
        assert result.is_dir()
        assert result == path

    def test_idempotent(self, tmp_path):
        from datacleaner.utils.file_utils import ensure_dir

        path = str(tmp_path / "exists")
        ensure_dir(path)
        ensure_dir(path)  # Should not raise
        assert Path(path).is_dir()

    def test_creates_parents(self, tmp_path):
        from datacleaner.utils.file_utils import ensure_dir

        deep = str(tmp_path / "x" / "y" / "z")
        ensure_dir(deep)
        assert Path(deep).parent.is_dir()
        assert Path(deep).parent.parent.is_dir()


# ============================================================
#  atomic_write
# ============================================================

class TestAtomicWrite:
    """Tests for atomic_write."""

    def test_writes_content(self, tmp_path):
        from datacleaner.utils.file_utils import atomic_write, read_text_safe

        path = str(tmp_path / "atom.txt")
        atomic_write(path, "atomic content")
        assert read_text_safe(path) == "atomic content"

    def test_creates_parent_dirs(self, tmp_path):
        from datacleaner.utils.file_utils import atomic_write

        path = str(tmp_path / "deep" / "nested" / "file.yaml")
        atomic_write(path, "data")
        assert Path(path).exists()

    def test_overwrites_existing(self, tmp_path):
        from datacleaner.utils.file_utils import atomic_write

        path = str(tmp_path / "existing.txt")
        Path(path).write_text("old")
        atomic_write(path, "new")
        assert Path(path).read_text() == "new"

    def test_atomic_does_not_leave_temp_files(self, tmp_path):
        from datacleaner.utils.file_utils import atomic_write

        target_dir = tmp_path / "target"
        target_dir.mkdir()
        path = str(target_dir / "important.txt")

        atomic_write(path, "data")

        # No .tmp files should remain
        tmp_files = list(target_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Leftover temp files: {tmp_files}"


# ============================================================
#  batch_rename
# ============================================================

class TestBatchRename:
    """Tests for batch_rename."""

    def test_rename_multiple(self, tmp_path):
        from datacleaner.utils.file_utils import batch_rename

        (tmp_path / "old_a.txt").write_text("a")
        (tmp_path / "old_b.txt").write_text("b")

        results = batch_rename(
            str(tmp_path),
            {"old_a.txt": "new_a.txt", "old_b.txt": "new_b.txt"},
        )

        assert results == [
            ("old_a.txt", "new_a.txt", True),
            ("old_b.txt", "new_b.txt", True),
        ]
        assert (tmp_path / "new_a.txt").exists()
        assert not (tmp_path / "old_a.txt").exists()

    def test_missing_source(self, tmp_path):
        from datacleaner.utils.file_utils import batch_rename

        results = batch_rename(str(tmp_path), {"doesnt_exist.txt": "nope.txt"})
        assert results[0][2] is False

    def test_destination_exists(self, tmp_path):
        from datacleaner.utils.file_utils import batch_rename

        (tmp_path / "source.txt").write_text("src")
        (tmp_path / "target.txt").write_text("dst")

        results = batch_rename(str(tmp_path), {"source.txt": "target.txt"})
        assert results[0][2] is False
        # Source should not have been moved
        assert (tmp_path / "source.txt").exists()

    def test_dry_run(self, tmp_path):
        from datacleaner.utils.file_utils import batch_rename

        (tmp_path / "real.txt").write_text("data")

        results = batch_rename(
            str(tmp_path),
            {"real.txt": "renamed.txt"},
            dry_run=True,
        )

        # Should report success but NOT actually rename
        assert results[0][2] is True
        assert (tmp_path / "real.txt").exists()
        assert not (tmp_path / "renamed.txt").exists()
