"""Unit tests for fuzzytail log cache service."""

import json
import time

import pytest

from fuzzytail.services.cache import LogCache


class TestLogCacheInit:
    """Tests for LogCache initialization."""

    @pytest.mark.unit
    def test_default_cache_dir(self, tmp_path: object) -> None:
        """LogCache should use ~/.cache/fuzzytail by default."""
        cache = LogCache()
        assert cache.cache_dir.name == "fuzzytail"
        assert cache.cache_dir.exists()

    @pytest.mark.unit
    def test_custom_cache_dir(self, tmp_path: object) -> None:
        """LogCache should accept a custom cache directory."""
        from pathlib import Path

        cache_dir = Path(str(tmp_path)) / "my-cache"
        cache = LogCache(cache_dir=cache_dir)
        assert cache.cache_dir == cache_dir
        assert cache_dir.exists()

    @pytest.mark.unit
    def test_xdg_cache_home(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LogCache should respect XDG_CACHE_HOME."""
        from pathlib import Path

        xdg_dir = Path(str(tmp_path)) / "xdg"
        monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_dir))
        cache = LogCache()
        assert cache.cache_dir == xdg_dir / "fuzzytail"


class TestLogCachePutGet:
    """Tests for put/get operations."""

    @pytest.mark.unit
    def test_put_and_get(self, tmp_path: object) -> None:
        """Should store and retrieve log content."""
        from pathlib import Path

        cache = LogCache(cache_dir=Path(str(tmp_path)) / "cache")
        url = "https://example.com/build/12345/builder-live.log"

        cache.put(url, "line 1\nline 2\n", byte_offset=14)
        content, offset = cache.get(url)

        assert content == "line 1\nline 2\n"
        assert offset == 14

    @pytest.mark.unit
    def test_get_missing_url(self, tmp_path: object) -> None:
        """Should return (None, 0) for uncached URLs."""
        from pathlib import Path

        cache = LogCache(cache_dir=Path(str(tmp_path)) / "cache")
        content, offset = cache.get("https://example.com/nonexistent.log")

        assert content is None
        assert offset == 0

    @pytest.mark.unit
    def test_put_overwrite(self, tmp_path: object) -> None:
        """Putting the same URL again should overwrite."""
        from pathlib import Path

        cache = LogCache(cache_dir=Path(str(tmp_path)) / "cache")
        url = "https://example.com/build/12345/builder-live.log"

        cache.put(url, "first", byte_offset=5)
        cache.put(url, "first\nsecond", byte_offset=12)

        content, offset = cache.get(url)
        assert content == "first\nsecond"
        assert offset == 12

    @pytest.mark.unit
    def test_completed_flag(self, tmp_path: object) -> None:
        """is_completed should reflect the completed flag."""
        from pathlib import Path

        cache = LogCache(cache_dir=Path(str(tmp_path)) / "cache")
        url = "https://example.com/build/12345/builder-live.log"

        cache.put(url, "content", byte_offset=7, completed=False)
        assert cache.is_completed(url) is False

        cache.put(url, "content", byte_offset=7, completed=True)
        assert cache.is_completed(url) is True

    @pytest.mark.unit
    def test_is_completed_missing(self, tmp_path: object) -> None:
        """is_completed should return False for uncached URLs."""
        from pathlib import Path

        cache = LogCache(cache_dir=Path(str(tmp_path)) / "cache")
        assert cache.is_completed("https://example.com/nope.log") is False


class TestLogCachePrune:
    """Tests for cache pruning."""

    @pytest.mark.unit
    def test_prune_old_entries(self, tmp_path: object) -> None:
        """Entries older than max_age should be pruned."""
        from pathlib import Path

        cache_dir = Path(str(tmp_path)) / "cache"
        cache = LogCache(cache_dir=cache_dir, max_age=60.0)
        url = "https://example.com/old.log"

        # Manually write an old entry
        key = LogCache._url_key(url)
        data_path = cache_dir / f"{key}.log"
        meta_path = cache_dir / f"{key}.meta"
        data_path.write_text("old content", encoding="utf-8")
        meta = {"url": url, "byte_offset": 11, "timestamp": time.time() - 120}
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        removed = cache.prune()
        assert removed == 1
        assert not data_path.exists()
        assert not meta_path.exists()

    @pytest.mark.unit
    def test_prune_keeps_fresh_entries(self, tmp_path: object) -> None:
        """Fresh entries should survive pruning."""
        from pathlib import Path

        cache_dir = Path(str(tmp_path)) / "cache"
        cache = LogCache(cache_dir=cache_dir, max_age=3600.0)
        url = "https://example.com/fresh.log"

        cache.put(url, "fresh content", byte_offset=13)
        removed = cache.prune()

        assert removed == 0
        content, offset = cache.get(url)
        assert content == "fresh content"

    @pytest.mark.unit
    def test_prune_corrupt_meta(self, tmp_path: object) -> None:
        """Corrupt meta files should be cleaned up on prune."""
        from pathlib import Path

        cache_dir = Path(str(tmp_path)) / "cache"
        cache = LogCache(cache_dir=cache_dir)

        meta_path = cache_dir / "badhash.meta"
        meta_path.write_text("NOT JSON", encoding="utf-8")

        removed = cache.prune()
        assert removed == 1
        assert not meta_path.exists()


class TestLogCacheClear:
    """Tests for cache clear."""

    @pytest.mark.unit
    def test_clear_all(self, tmp_path: object) -> None:
        """clear() should remove all entries."""
        from pathlib import Path

        cache_dir = Path(str(tmp_path)) / "cache"
        cache = LogCache(cache_dir=cache_dir)

        cache.put("https://example.com/a.log", "a", byte_offset=1)
        cache.put("https://example.com/b.log", "b", byte_offset=1)

        removed = cache.clear()
        assert removed == 2

        assert cache.get("https://example.com/a.log") == (None, 0)
        assert cache.get("https://example.com/b.log") == (None, 0)


class TestLogCacheExpiry:
    """Tests for expiry during get()."""

    @pytest.mark.unit
    def test_get_expired_entry(self, tmp_path: object) -> None:
        """Expired entries should return (None, 0) and be cleaned up."""
        from pathlib import Path

        cache_dir = Path(str(tmp_path)) / "cache"
        cache = LogCache(cache_dir=cache_dir, max_age=60.0)
        url = "https://example.com/expired.log"

        # Manually write an expired entry
        key = LogCache._url_key(url)
        data_path = cache_dir / f"{key}.log"
        meta_path = cache_dir / f"{key}.meta"
        data_path.write_text("expired content", encoding="utf-8")
        meta = {"url": url, "byte_offset": 15, "timestamp": time.time() - 120}
        meta_path.write_text(json.dumps(meta), encoding="utf-8")

        content, offset = cache.get(url)
        assert content is None
        assert offset == 0
        assert not data_path.exists()


class TestLogCacheUrlKey:
    """Tests for the URL key hashing."""

    @pytest.mark.unit
    def test_url_key_deterministic(self) -> None:
        """Same URL should always produce the same key."""
        url = "https://example.com/build/12345/builder-live.log"
        assert LogCache._url_key(url) == LogCache._url_key(url)

    @pytest.mark.unit
    def test_url_key_different_urls(self) -> None:
        """Different URLs should produce different keys."""
        key1 = LogCache._url_key("https://example.com/a.log")
        key2 = LogCache._url_key("https://example.com/b.log")
        assert key1 != key2
