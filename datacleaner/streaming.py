"""Streaming mode router and chunked I/O primitives.

Decides whether a file should use streaming (chunked) or in-memory
processing based on file size. Used by scan and scrub-dump commands.
"""

from pathlib import Path

_MEGABYTE = 1024 * 1024


class StreamingRouter:
    """Decides whether a file should use streaming or in-memory processing.

    Files under the threshold use the existing fast in-memory path.
    Files over the threshold are routed to chunked/streaming processors
    to avoid OOM on large datasets.
    """

    def __init__(self, threshold_mb: int = 100):
        self.threshold_bytes = threshold_mb * _MEGABYTE

    def should_stream(self, filepath: str | Path) -> bool:
        """Return True if file exceeds the streaming threshold.

        Returns False for non-existent files or files under the threshold.
        """
        try:
            return Path(filepath).stat().st_size > self.threshold_bytes
        except OSError:
            return False  # can't stat? assume small / not a real file
