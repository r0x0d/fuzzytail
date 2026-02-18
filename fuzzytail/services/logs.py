"""Service for streaming and following COPR build logs."""

from __future__ import annotations

import gzip
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import httpx

from fuzzytail.models import BuildLog
from fuzzytail.services.cache import LogCache


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
        cache: LogCache | None = None,
    ):
        """Initialize the log streamer.

        Args:
            poll_interval: Seconds between poll attempts for live logs.
            timeout: HTTP request timeout in seconds.
            max_retries: Maximum number of retries for failed requests.
            cache: Optional disk cache for persisting log content across
                   restarts.  When provided, cached content is used as
                   the starting point so only new bytes are fetched.
        """
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.Client | None = None
        self._positions: dict[str, int] = {}
        self._completed: set[str] = set()
        self._cache = cache
        self._cached_content: dict[str, str] = {}  # url -> accumulated content

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

    def __enter__(self) -> LogStreamer:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_log(self, log: BuildLog, byte_offset: int = 0) -> str | None:
        """Fetch content of a log file, optionally from a byte offset.

        Tries live log first (.log), then compressed (.log.gz).

        Args:
            log: The BuildLog to fetch.
            byte_offset: Byte position to start from (uses Range header).

        Returns:
            Log content as string, or None if not available.
        """
        # Try live log URL first
        content = self._fetch_url(log.url, byte_offset=byte_offset)
        if content is not None:
            return content

        # Try compressed version (always fetches full content)
        gz_url = f"{log.url}.gz"
        content = self._fetch_url(gz_url, compressed=True)
        if content is not None:
            # Mark as completed since it's compressed
            self._completed.add(log.url)
            # If we had an offset, slice the decompressed content
            if byte_offset > 0:
                return content[byte_offset:] if len(content) > byte_offset else None
        return content

    def _fetch_url(
        self,
        url: str,
        compressed: bool = False,
        byte_offset: int = 0,
    ) -> str | None:
        """Fetch content from a URL, optionally using HTTP Range requests.

        Args:
            url: The URL to fetch.
            compressed: Whether the content is gzip compressed.
            byte_offset: Byte position to start from (uses Range header).
                         Ignored when ``compressed`` is True.

        Returns:
            Content as string, or None if not available.
        """
        headers: dict[str, str] = {}
        if byte_offset > 0 and not compressed:
            headers["Range"] = f"bytes={byte_offset}-"

        for attempt in range(self.max_retries):
            try:
                response = self.client.get(url, headers=headers)
                if response.status_code == 404:
                    return None

                # 206 Partial Content is the expected Range response
                if response.status_code == 206:
                    return response.text

                response.raise_for_status()

                if compressed:
                    # Try to decompress, but fall back to plain text if not gzipped
                    try:
                        return gzip.decompress(response.content).decode("utf-8")
                    except gzip.BadGzipFile:
                        # Not actually gzipped, try as plain text
                        return response.text

                # Server ignored Range header (returned 200 instead of 206)
                # Slice manually from the offset
                if byte_offset > 0:
                    text = response.text
                    if len(text) <= byte_offset:
                        return None
                    return text[byte_offset:]

                return response.text

            except httpx.HTTPStatusError:
                if attempt == self.max_retries - 1:
                    return None
            except httpx.RequestError:
                if attempt == self.max_retries - 1:
                    return None
                time.sleep(0.5)

        return None

    def _restore_from_cache(self, url: str) -> None:
        """Seed position and accumulated content from the disk cache."""
        if self._cache is None or url in self._positions:
            return

        cached_content, byte_offset = self._cache.get(url)
        if cached_content is not None:
            self._positions[url] = byte_offset
            self._cached_content[url] = cached_content
            if self._cache.is_completed(url):
                self._completed.add(url)

    def _persist_to_cache(
        self, url: str, new_content: str, *, completed: bool = False
    ) -> None:
        """Append *new_content* to the accumulated cache on disk."""
        if self._cache is None:
            return
        accumulated = self._cached_content.get(url, "") + new_content
        self._cached_content[url] = accumulated
        self._cache.put(
            url,
            accumulated,
            self._positions.get(url, len(accumulated)),
            completed=completed,
        )

    def get_new_content(self, log: BuildLog) -> LogChunk | None:
        """Get new content since last fetch for a log.

        Uses HTTP Range requests when possible to avoid re-downloading
        the entire log on every poll.  Results are persisted to the
        disk cache (if configured) so restarts can pick up where they
        left off.

        Args:
            log: The BuildLog to check for new content.

        Returns:
            LogChunk with new content, or None if no new content.
        """
        if log.url in self._completed:
            return None

        # Seed from disk cache on first access
        self._restore_from_cache(log.url)

        last_pos = self._positions.get(log.url, 0)

        # Try incremental fetch first (Range request)
        new_content = self._fetch_url(log.url, byte_offset=last_pos)
        is_completed = False
        if new_content is None:
            # Fall back to compressed version if live log not available
            gz_url = f"{log.url}.gz"
            full_content = self._fetch_url(gz_url, compressed=True)
            if full_content is not None:
                self._completed.add(log.url)
                is_completed = True
                if len(full_content) <= last_pos:
                    return None
                new_content = full_content[last_pos:]
            else:
                return None

        if not new_content:
            return None

        self._positions[log.url] = last_pos + len(new_content)
        self._persist_to_cache(log.url, new_content, completed=is_completed)

        return LogChunk(
            log=log,
            content=new_content,
            is_new=True,
        )

    def get_new_content_batch(
        self,
        logs: list[BuildLog],
        max_workers: int = 4,
    ) -> list[LogChunk]:
        """Fetch new content for multiple logs concurrently.

        Args:
            logs: List of BuildLog objects to check.
            max_workers: Maximum number of parallel HTTP requests.

        Returns:
            List of LogChunk objects with new content (empty if none).
        """
        if not logs:
            return []

        # For a single log, skip the thread pool overhead
        if len(logs) == 1:
            chunk = self.get_new_content(logs[0])
            return [chunk] if chunk else []

        results: list[LogChunk] = []

        with ThreadPoolExecutor(max_workers=min(max_workers, len(logs))) as pool:
            futures = {pool.submit(self.get_new_content, log): log for log in logs}
            for future in as_completed(futures):
                try:
                    chunk = future.result()
                    if chunk:
                        results.append(chunk)
                except Exception:
                    pass

        return results

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
