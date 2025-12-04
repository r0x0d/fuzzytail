"""Service for streaming and following COPR build logs."""

import gzip
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

import httpx

from fuzzytail.models import BuildLog, BuildLogType, LogSource


@dataclass
class LogChunk:
    """A chunk of log content."""

    log: BuildLog
    content: str
    is_new: bool = True
    timestamp: float = field(default_factory=time.time)


class LogStreamer:
    """Service for streaming build logs in real-time."""

    def __init__(
        self,
        poll_interval: float = 2.0,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        """Initialize the log streamer.

        Args:
            poll_interval: Seconds between poll attempts for live logs.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
        """
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.Client] = None
        self._positions: dict[str, int] = {}
        self._completed: set[str] = set()

    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "LogStreamer":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_log(self, log: BuildLog) -> Optional[str]:
        """Fetch the complete content of a log file.

        Tries live log first (.log), then compressed (.log.gz).

        Args:
            log: The BuildLog to fetch.

        Returns:
            Log content as string, or None if not available.
        """
        # Try live log URL first
        content = self._fetch_url(log.url)
        if content is not None:
            return content

        # Try compressed version
        gz_url = f"{log.url}.gz"
        content = self._fetch_url(gz_url, compressed=True)
        if content is not None:
            # Mark as completed since it's compressed
            self._completed.add(log.url)
        return content

    def _fetch_url(self, url: str, compressed: bool = False) -> Optional[str]:
        """Fetch content from a URL.

        Args:
            url: The URL to fetch.
            compressed: Whether the content is gzip compressed.

        Returns:
            Content as string, or None if not available.
        """
        for attempt in range(self.max_retries):
            try:
                response = self.client.get(url)
                if response.status_code == 404:
                    return None
                response.raise_for_status()

                if compressed:
                    # Try to decompress, but fall back to plain text if not gzipped
                    try:
                        return gzip.decompress(response.content).decode("utf-8")
                    except gzip.BadGzipFile:
                        # Not actually gzipped, try as plain text
                        return response.text
                return response.text

            except httpx.HTTPStatusError:
                if attempt == self.max_retries - 1:
                    return None
            except httpx.RequestError:
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(0.5)

        return None

    def get_new_content(self, log: BuildLog) -> Optional[LogChunk]:
        """Get new content since last fetch for a log.

        Args:
            log: The BuildLog to check for new content.

        Returns:
            LogChunk with new content, or None if no new content.
        """
        if log.url in self._completed:
            return None

        content = self.fetch_log(log)
        if content is None:
            return None

        last_pos = self._positions.get(log.url, 0)
        if len(content) <= last_pos:
            return None

        new_content = content[last_pos:]
        self._positions[log.url] = len(content)

        return LogChunk(
            log=log,
            content=new_content,
            is_new=True,
        )

    def is_log_complete(self, log: BuildLog) -> bool:
        """Check if a log file is complete (compressed version exists).

        Args:
            log: The BuildLog to check.

        Returns:
            True if the log is complete, False otherwise.
        """
        if log.url in self._completed:
            return True

        # Check if compressed version exists
        gz_url = f"{log.url}.gz"
        try:
            response = self.client.head(gz_url)
            if response.status_code == 200:
                self._completed.add(log.url)
                return True
        except httpx.RequestError:
            pass

        return False

    def stream_logs(
        self,
        logs: list[BuildLog],
        on_chunk: Callable[[LogChunk], None],
        stop_condition: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Stream multiple logs, calling callback with new content.

        Args:
            logs: List of BuildLog objects to stream.
            on_chunk: Callback function for each new log chunk.
            stop_condition: Optional function that returns True to stop streaming.
        """
        active_logs = list(logs)

        while active_logs:
            if stop_condition and stop_condition():
                break

            for log in list(active_logs):
                chunk = self.get_new_content(log)
                if chunk:
                    on_chunk(chunk)

                # Check if log is complete
                if self.is_log_complete(log):
                    # Fetch any remaining content
                    final_chunk = self.get_new_content(log)
                    if final_chunk:
                        on_chunk(final_chunk)
                    active_logs.remove(log)

            if active_logs:
                _interruptible_sleep(self.poll_interval)

    def iter_log_chunks(
        self,
        logs: list[BuildLog],
        stop_condition: Optional[Callable[[], bool]] = None,
    ) -> Iterator[LogChunk]:
        """Iterate over log chunks as they become available.

        Args:
            logs: List of BuildLog objects to stream.
            stop_condition: Optional function that returns True to stop streaming.

        Yields:
            LogChunk objects as new content becomes available.
        """
        active_logs = list(logs)

        while active_logs:
            if stop_condition and stop_condition():
                break

            for log in list(active_logs):
                chunk = self.get_new_content(log)
                if chunk:
                    yield chunk

                if self.is_log_complete(log):
                    final_chunk = self.get_new_content(log)
                    if final_chunk:
                        yield final_chunk
                    active_logs.remove(log)

            if active_logs:
                _interruptible_sleep(self.poll_interval)


def _interruptible_sleep(seconds: float, interval: float = 0.1) -> None:
    """Sleep that can be interrupted by KeyboardInterrupt.

    Args:
        seconds: Total seconds to sleep.
        interval: Check interval for interrupts.
    """
    elapsed = 0.0
    while elapsed < seconds:
        time.sleep(min(interval, seconds - elapsed))
        elapsed += interval


def categorize_logs(
    logs: list[BuildLog],
    log_types: Optional[list[BuildLogType]] = None,
    sources: Optional[list[LogSource]] = None,
    chroots: Optional[list[str]] = None,
) -> list[BuildLog]:
    """Filter and categorize logs based on criteria.

    Args:
        logs: List of all available logs.
        log_types: Filter by log types (import, builder-live, backend).
        sources: Filter by log sources (import, srpm, rpm).
        chroots: Filter by chroot names.

    Returns:
        Filtered list of BuildLog objects.
    """
    filtered = logs

    if log_types:
        filtered = [entry for entry in filtered if entry.log_type in log_types]

    if sources:
        filtered = [entry for entry in filtered if entry.source in sources]

    if chroots:
        # Import and SRPM logs are not chroot-specific, always include them
        filtered = [
            entry
            for entry in filtered
            if entry.source in (LogSource.IMPORT, LogSource.SRPM)
            or entry.chroot in chroots
        ]

    return filtered
