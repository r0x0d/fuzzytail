"""Unit tests for fuzzytail logs service."""

import httpx
import pytest
from pytest_mock import MockerFixture

from fuzzytail.models import BuildLog, BuildLogType, LogSource
from fuzzytail.services.logs import (
    LogChunk,
    LogStreamer,
    _interruptible_sleep,
    categorize_logs,
)


class TestLogChunk:
    """Tests for LogChunk dataclass."""

    @pytest.mark.unit
    def test_create_log_chunk(self, sample_build_log: BuildLog) -> None:
        """Test creating a LogChunk instance."""
        chunk = LogChunk(
            log=sample_build_log,
            content="test content",
            is_new=True,
        )
        assert chunk.log == sample_build_log
        assert chunk.content == "test content"
        assert chunk.is_new is True
        assert chunk.timestamp > 0

    @pytest.mark.unit
    def test_log_chunk_default_values(self, sample_build_log: BuildLog) -> None:
        """Test LogChunk default values."""
        chunk = LogChunk(log=sample_build_log, content="content")
        assert chunk.is_new is True


class TestLogStreamer:
    """Tests for LogStreamer class."""

    @pytest.mark.unit
    def test_init_defaults(self) -> None:
        """Test default initialization."""
        streamer = LogStreamer()
        assert streamer.poll_interval == 2.0
        assert streamer.timeout == 10.0
        assert streamer.max_retries == 3
        assert streamer._client is None

    @pytest.mark.unit
    def test_init_custom_values(self) -> None:
        """Test custom initialization."""
        streamer = LogStreamer(poll_interval=5.0, timeout=30.0, max_retries=5)
        assert streamer.poll_interval == 5.0
        assert streamer.timeout == 30.0
        assert streamer.max_retries == 5

    @pytest.mark.unit
    def test_client_property(self) -> None:
        """Test client property creates httpx.Client."""
        streamer = LogStreamer()
        try:
            client = streamer.client
            assert isinstance(client, httpx.Client)
            assert streamer._client is client
        finally:
            streamer.close()

    @pytest.mark.unit
    def test_close(self) -> None:
        """Test close method."""
        streamer = LogStreamer()
        _ = streamer.client
        streamer.close()
        assert streamer._client is None

    @pytest.mark.unit
    def test_context_manager(self) -> None:
        """Test context manager protocol."""
        with LogStreamer() as streamer:
            _ = streamer.client
            assert streamer._client is not None
        assert streamer._client is None

    @pytest.mark.unit
    def test_fetch_log_success(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test fetch_log returns content on success."""
        streamer = LogStreamer()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "log content here"
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(streamer, "_client", mock_client)

        content = streamer.fetch_log(sample_build_log)

        assert content == "log content here"

    @pytest.mark.unit
    def test_fetch_log_404_tries_gz(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test fetch_log tries .gz file on 404."""
        streamer = LogStreamer()

        mock_client = mocker.MagicMock()

        # First call returns 404, second (gz) returns content
        mock_response_404 = mocker.MagicMock()
        mock_response_404.status_code = 404

        mock_response_gz = mocker.MagicMock()
        mock_response_gz.status_code = 200
        mock_response_gz.text = "compressed content"
        mock_response_gz.content = b"compressed content"
        mock_response_gz.raise_for_status = mocker.MagicMock()

        mock_client.get.side_effect = [mock_response_404, mock_response_gz]

        mocker.patch.object(streamer, "_client", mock_client)

        content = streamer.fetch_log(sample_build_log)

        assert content == "compressed content"
        assert sample_build_log.url in streamer._completed

    @pytest.mark.unit
    def test_fetch_log_not_found(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test fetch_log returns None when not found."""
        streamer = LogStreamer()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 404
        mock_client.get.return_value = mock_response

        mocker.patch.object(streamer, "_client", mock_client)

        content = streamer.fetch_log(sample_build_log)

        assert content is None

    @pytest.mark.unit
    def test_fetch_url_retries_on_error(self, mocker: MockerFixture) -> None:
        """Test _fetch_url retries on request error."""
        streamer = LogStreamer(max_retries=3)

        mock_client = mocker.MagicMock()

        # Fail twice, succeed on third
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "content"
        mock_response.raise_for_status = mocker.MagicMock()

        mock_client.get.side_effect = [
            httpx.RequestError("Error 1"),
            httpx.RequestError("Error 2"),
            mock_response,
        ]

        mocker.patch.object(streamer, "_client", mock_client)
        mocker.patch("time.sleep")  # Speed up test

        content = streamer._fetch_url("http://example.com/log")

        assert content == "content"
        assert mock_client.get.call_count == 3

    @pytest.mark.unit
    def test_get_new_content_first_fetch(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test get_new_content on first fetch."""
        streamer = LogStreamer()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "line 1\nline 2\n"
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(streamer, "_client", mock_client)

        chunk = streamer.get_new_content(sample_build_log)

        assert chunk is not None
        assert chunk.content == "line 1\nline 2\n"
        assert streamer._positions[sample_build_log.url] == 14

    @pytest.mark.unit
    def test_get_new_content_incremental(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test get_new_content returns only new content."""
        streamer = LogStreamer()
        streamer._positions[sample_build_log.url] = 5

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "12345NEW CONTENT"
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(streamer, "_client", mock_client)

        chunk = streamer.get_new_content(sample_build_log)

        assert chunk is not None
        assert chunk.content == "NEW CONTENT"

    @pytest.mark.unit
    def test_get_new_content_no_new_data(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test get_new_content returns None when no new data."""
        streamer = LogStreamer()
        streamer._positions[sample_build_log.url] = 10

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_response.text = "1234567890"  # Same length as position
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(streamer, "_client", mock_client)

        chunk = streamer.get_new_content(sample_build_log)

        assert chunk is None

    @pytest.mark.unit
    def test_get_new_content_completed_log(self, sample_build_log: BuildLog) -> None:
        """Test get_new_content returns None for completed logs."""
        streamer = LogStreamer()
        streamer._completed.add(sample_build_log.url)

        chunk = streamer.get_new_content(sample_build_log)

        assert chunk is None

    @pytest.mark.unit
    def test_is_log_complete_already_completed(
        self, sample_build_log: BuildLog
    ) -> None:
        """Test is_log_complete returns True for already completed logs."""
        streamer = LogStreamer()
        streamer._completed.add(sample_build_log.url)

        assert streamer.is_log_complete(sample_build_log) is True

    @pytest.mark.unit
    def test_is_log_complete_gz_exists(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test is_log_complete returns True when .gz file exists."""
        streamer = LogStreamer()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 200
        mock_client.head.return_value = mock_response

        mocker.patch.object(streamer, "_client", mock_client)

        is_complete = streamer.is_log_complete(sample_build_log)

        assert is_complete is True
        assert sample_build_log.url in streamer._completed

    @pytest.mark.unit
    def test_is_log_complete_gz_not_exists(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test is_log_complete returns False when .gz doesn't exist."""
        streamer = LogStreamer()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.status_code = 404
        mock_client.head.return_value = mock_response

        mocker.patch.object(streamer, "_client", mock_client)

        is_complete = streamer.is_log_complete(sample_build_log)

        assert is_complete is False


class TestCategorizeLogs:
    """Tests for categorize_logs function."""

    @pytest.fixture
    def mixed_logs(self) -> list[BuildLog]:
        """Create a mixed list of logs for testing."""
        return [
            BuildLog(
                build_id=1,
                log_type=BuildLogType.IMPORT,
                source=LogSource.IMPORT,
                url="http://example.com/import.log",
            ),
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BACKEND,
                source=LogSource.SRPM,
                url="http://example.com/srpm-backend.log",
            ),
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BUILDER_LIVE,
                source=LogSource.SRPM,
                url="http://example.com/srpm-builder-live.log",
            ),
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BACKEND,
                source=LogSource.RPM,
                chroot="fedora-43-x86_64",
                url="http://example.com/rpm-backend.log",
            ),
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BUILDER_LIVE,
                source=LogSource.RPM,
                chroot="fedora-42-x86_64",
                url="http://example.com/rpm-builder-live.log",
            ),
        ]

    @pytest.mark.unit
    def test_categorize_logs_no_filters(self, mixed_logs: list[BuildLog]) -> None:
        """Test categorize_logs returns all logs with no filters."""
        result = categorize_logs(mixed_logs)
        assert len(result) == 5

    @pytest.mark.unit
    def test_categorize_logs_filter_by_log_type(
        self, mixed_logs: list[BuildLog]
    ) -> None:
        """Test filtering by log type."""
        result = categorize_logs(mixed_logs, log_types=[BuildLogType.BACKEND])
        assert len(result) == 2
        for log in result:
            assert log.log_type == BuildLogType.BACKEND

    @pytest.mark.unit
    def test_categorize_logs_filter_by_source(self, mixed_logs: list[BuildLog]) -> None:
        """Test filtering by source."""
        result = categorize_logs(mixed_logs, sources=[LogSource.SRPM])
        assert len(result) == 2
        for log in result:
            assert log.source == LogSource.SRPM

    @pytest.mark.unit
    def test_categorize_logs_filter_by_chroot(self, mixed_logs: list[BuildLog]) -> None:
        """Test filtering by chroot includes import and SRPM logs."""
        result = categorize_logs(mixed_logs, chroots=["fedora-43-x86_64"])
        # Should include import (1) + SRPM (2) + matching RPM (1) = 4
        assert len(result) == 4

    @pytest.mark.unit
    def test_categorize_logs_combined_filters(self, mixed_logs: list[BuildLog]) -> None:
        """Test combining multiple filters."""
        result = categorize_logs(
            mixed_logs,
            log_types=[BuildLogType.BUILDER_LIVE],
            sources=[LogSource.RPM],
        )
        assert len(result) == 1
        assert result[0].chroot == "fedora-42-x86_64"


class TestInterruptibleSleep:
    """Tests for _interruptible_sleep function."""

    @pytest.mark.unit
    def test_interruptible_sleep(self) -> None:
        """Test _interruptible_sleep completes in expected time."""
        import time

        start = time.time()
        _interruptible_sleep(0.2, interval=0.05)
        elapsed = time.time() - start

        assert 0.15 < elapsed < 0.4  # Allow some tolerance
