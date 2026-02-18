"""Disk-based cache for COPR build logs.

Caches fetched log content under ``~/.cache/fuzzytail/`` (or
``$XDG_CACHE_HOME/fuzzytail/``) so that restarting fuzzytail does not
re-download logs that were already fetched.  Entries older than 7 days
are pruned automatically on startup.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

#: Default maximum age for cache entries (7 days in seconds).
DEFAULT_MAX_AGE_SECONDS: float = 7 * 24 * 3600


class LogCache:
    """Disk-based log cache with automatic expiry.

    Each cached log is stored as two files:

    - ``<hash>.log`` -- the raw (potentially partial) log content
    - ``<hash>.meta`` -- a small JSON sidecar with metadata

    The *hash* is the SHA-256 hex digest of the log URL.
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        max_age: float = DEFAULT_MAX_AGE_SECONDS,
    ) -> None:
        if cache_dir is not None:
            self._cache_dir = Path(cache_dir)
        else:
            xdg = os.environ.get("XDG_CACHE_HOME")
            base = Path(xdg) if xdg else Path.home() / ".cache"
            self._cache_dir = base / "fuzzytail"

        self._max_age = max_age
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def cache_dir(self) -> Path:
        """Return the resolved cache directory."""
        return self._cache_dir

    def prune(self) -> int:
        """Remove cache entries older than *max_age* seconds.

        Returns:
            Number of entries removed.
        """
        now = time.time()
        removed = 0
        for meta_path in self._cache_dir.glob("*.meta"):
            try:
                meta = self._read_meta(meta_path)
                if now - meta.get("timestamp", 0) > self._max_age:
                    self._remove_entry(meta_path)
                    removed += 1
            except Exception:
                # Corrupt entry -- remove it
                self._remove_entry(meta_path)
                removed += 1
        return removed

    def get(self, url: str) -> tuple[str | None, int]:
        """Retrieve cached content and the stored byte offset.

        Args:
            url: The original log URL used as cache key.

        Returns:
            A ``(content, byte_offset)`` tuple.  If the URL is not
            cached, returns ``(None, 0)``.
        """
        key = self._url_key(url)
        meta_path = self._cache_dir / f"{key}.meta"
        data_path = self._cache_dir / f"{key}.log"

        if not meta_path.exists() or not data_path.exists():
            return None, 0

        try:
            meta = self._read_meta(meta_path)
            # Check expiry
            if time.time() - meta.get("timestamp", 0) > self._max_age:
                self._remove_entry(meta_path)
                return None, 0

            content = data_path.read_text(encoding="utf-8")
            offset = int(meta.get("byte_offset", 0))
            return content, offset
        except Exception:
            self._remove_entry(meta_path)
            return None, 0

    def put(
        self,
        url: str,
        content: str,
        byte_offset: int,
        *,
        completed: bool = False,
    ) -> None:
        """Store (or update) a cache entry.

        Args:
            url: The log URL.
            content: The **full accumulated** log content so far.
            byte_offset: Number of bytes fetched so far.
            completed: Whether the log is fully fetched (compressed
                       version found, build finished, etc.).
        """
        key = self._url_key(url)
        data_path = self._cache_dir / f"{key}.log"
        meta_path = self._cache_dir / f"{key}.meta"

        data_path.write_text(content, encoding="utf-8")
        meta = {
            "url": url,
            "byte_offset": byte_offset,
            "timestamp": time.time(),
            "completed": completed,
        }
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

    def is_completed(self, url: str) -> bool:
        """Check whether a cached log is marked as fully fetched."""
        key = self._url_key(url)
        meta_path = self._cache_dir / f"{key}.meta"
        if not meta_path.exists():
            return False
        try:
            meta = self._read_meta(meta_path)
            return bool(meta.get("completed", False))
        except Exception:
            return False

    def clear(self) -> int:
        """Remove **all** cache entries.

        Returns:
            Number of entries removed.
        """
        removed = 0
        for meta_path in self._cache_dir.glob("*.meta"):
            self._remove_entry(meta_path)
            removed += 1
        return removed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _url_key(url: str) -> str:
        """Derive a filesystem-safe cache key from a URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    @staticmethod
    def _read_meta(meta_path: Path) -> dict:
        """Read and parse a ``.meta`` JSON sidecar."""
        return json.loads(meta_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    @staticmethod
    def _remove_entry(meta_path: Path) -> None:
        """Remove a cache entry (both ``.meta`` and ``.log`` files)."""
        data_path = meta_path.with_suffix(".log")
        meta_path.unlink(missing_ok=True)
        data_path.unlink(missing_ok=True)
