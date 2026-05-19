"""Tests for streaming mode — chunked I/O for large files."""

import tempfile
from pathlib import Path
from datacleaner.config import load_config
from datacleaner.streaming import StreamingRouter


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

