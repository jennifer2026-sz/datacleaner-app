"""Tests for streaming mode — chunked I/O for large files."""

import tempfile
from pathlib import Path
from datacleaner.config import load_config
from datacleaner.streaming import StreamingRouter
from datacleaner.utils.streaming_readers import csv_chunked_reader, text_chunked_reader


class TestStreamingConfig:
    """Streaming configuration defaults."""

    def test_streaming_keys_exist(self):
        """Streaming config keys must exist with sensible defaults."""
        config = load_config()
        assert "streaming" in config
        assert config["streaming"]["chunk_rows"] == 10000
        assert config["streaming"]["chunk_bytes"] == 10_485_760
        assert config["streaming"]["auto_threshold_mb"] == 100

    def test_chunk_bytes_is_10mb(self):
        """chunk_bytes default should be exactly 10 MiB."""
        config = load_config()
        assert config["streaming"]["chunk_bytes"] == 10 * 1024 * 1024


class TestStreamingRouter:
    """File size gate for streaming routing."""

    def test_small_file_should_not_stream(self, tmp_path):
        """Files under threshold should use fast in-memory path."""
        f = tmp_path / "small.csv"
        f.write_text("a,b\n1,2\n" * 10)

        router = StreamingRouter(threshold_mb=1)
        assert not router.should_stream(f)

    def test_large_file_should_stream(self, tmp_path):
        """Files over threshold should trigger streaming."""
        f = tmp_path / "large.csv"
        f.write_bytes(b"x" * int(2.5 * 1024 * 1024))  # 2.5 MB

        router = StreamingRouter(threshold_mb=1)
        assert router.should_stream(f)

    def test_missing_file_returns_false(self, tmp_path):
        """Non-existent file should not trigger streaming."""
        router = StreamingRouter(threshold_mb=1)
        assert not router.should_stream(tmp_path / "does_not_exist.csv")

    def test_default_threshold_is_100mb(self):
        """Default threshold should be 100 MB."""
        router = StreamingRouter()
        assert router.threshold_bytes == 100 * 1024 * 1024


class TestCsvChunkedReader:
    """Streaming CSV reader — batch rows without loading entire file."""

    def test_yields_batches_of_chunk_size(self, tmp_path):
        """Should yield batches of exactly chunk_size rows."""
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
        assert len(chunks) == 3  # 25 rows / 10 = 3 batches
        assert len(chunks[0]) == 10
        assert len(chunks[1]) == 10
        assert len(chunks[2]) == 5

    def test_first_row_is_correct(self, tmp_path):
        """First yielded row should match first data row."""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("name,email\nAlice,a@b.com\nBob,b@c.com\n")

        for h, batch in csv_chunked_reader(csv_path, chunk_size=10):
            assert batch[0] == {"name": "Alice", "email": "a@b.com"}
            break

    def test_empty_file_except_header(self, tmp_path):
        """CSV with only header should yield no batches."""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("a,b,c\n")

        chunks = list(csv_chunked_reader(csv_path, chunk_size=10))
        assert len(chunks) == 0

    def test_unicode_values(self, tmp_path):
        """Should handle Chinese characters in CSV."""
        csv_path = tmp_path / "test.csv"
        csv_path.write_text("name,city\n张三,深圳\n李四,北京\n", encoding="utf-8")

        for h, batch in csv_chunked_reader(csv_path, chunk_size=10):
            assert batch[0]["name"] == "张三"
            assert batch[0]["city"] == "深圳"
            break

    def test_encoding_fallback(self, tmp_path):
        """Should handle Latin-1 encoded CSV."""
        csv_path = tmp_path / "test.csv"
        # Write as latin-1
        csv_path.write_bytes("name,value\ncafé,100\n".encode("latin-1"))

        for h, batch in csv_chunked_reader(csv_path, chunk_size=10, encoding="latin-1"):
            assert batch[0]["name"] == "café"
            break


class TestTextChunkedReader:
    """Streaming text reader — overlapping chunks for PII continuity."""

    def test_yields_overlapping_chunks(self, tmp_path):
        """Chunks should overlap by overlap_bytes for PII continuity."""
        # 50 chars of predictable text
        text = "ABCDEFGHIJ" * 5  # 50 chars
        txt_path = tmp_path / "test.txt"
        txt_path.write_text(text)

        chunks = list(text_chunked_reader(
            txt_path, chunk_bytes=20, overlap_bytes=5,
        ))

        # 50 bytes / (20-5) = ~4 chunks
        assert len(chunks) >= 3
        # First chunk has bytes 0-19 + carry
        assert chunks[0].startswith("ABCDEFGHIJ")
        # Chunk 2 should contain the overlap from chunk 1
        assert text[15:25] in chunks[1]

    def test_small_file_one_chunk(self, tmp_path):
        """File smaller than chunk_bytes should yield one chunk."""
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("short text")

        chunks = list(text_chunked_reader(txt_path, chunk_bytes=1024))
        assert len(chunks) == 1
        assert chunks[0] == "short text"

    def test_chinese_text(self, tmp_path):
        """Should handle multi-byte UTF-8 correctly."""
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("用户张三的邮箱是zhangsan@example.com，电话13800138000\n")

        chunks = list(text_chunked_reader(txt_path, chunk_bytes=1024))
        assert "zhangsan@example.com" in chunks[0]
        assert "13800138000" in chunks[0]
