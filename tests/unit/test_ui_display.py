"""Unit tests for fuzzytail UI display."""

import pytest
from pytest_mock import MockerFixture
from rich.console import Console
from rich.text import Text

from fuzzytail.models import Build, BuildLog, BuildLogType, LogSource
from fuzzytail.services.logs import LogChunk
from fuzzytail.ui.display import (
    LogDisplay,
    list_builds,
    print_build_summary,
)


class TestLogDisplay:
    """Tests for LogDisplay class."""

    @pytest.mark.unit
    def test_init_defaults(self) -> None:
        """Test default initialization."""
        display = LogDisplay()
        assert display.show_import is True
        assert display.show_srpm is True
        assert display.show_rpm is True
        assert display.log_types is None
        assert display.chroots is None
        assert display._stop is False

    @pytest.mark.unit
    def test_init_custom_values(self) -> None:
        """Test custom initialization."""
        console = Console()
        display = LogDisplay(
            console=console,
            show_import=False,
            show_srpm=False,
            show_rpm=True,
            log_types=[BuildLogType.BUILDER_LIVE],
            chroots=["fedora-43-x86_64"],
        )
        assert display.console is console
        assert display.show_import is False
        assert display.show_srpm is False
        assert display.show_rpm is True
        assert display.log_types == [BuildLogType.BUILDER_LIVE]
        assert display.chroots == ["fedora-43-x86_64"]

    @pytest.mark.unit
    def test_filter_logs(self, sample_build: Build) -> None:
        """Test _filter_logs method."""
        display = LogDisplay(show_import=True, show_srpm=True, show_rpm=True)
        all_logs = sample_build.get_all_log_urls()
        filtered = display._filter_logs(all_logs)

        # Should include all logs
        assert len(filtered) == len(all_logs)

    @pytest.mark.unit
    def test_filter_logs_srpm_only(self, sample_build: Build) -> None:
        """Test _filter_logs with SRPM only."""
        display = LogDisplay(show_import=False, show_srpm=True, show_rpm=False)
        all_logs = sample_build.get_all_log_urls()
        filtered = display._filter_logs(all_logs)

        for log in filtered:
            assert log.source == LogSource.SRPM

    @pytest.mark.unit
    def test_filter_logs_by_log_type(self, sample_build: Build) -> None:
        """Test _filter_logs by log type."""
        display = LogDisplay(log_types=[BuildLogType.BUILDER_LIVE])
        all_logs = sample_build.get_all_log_urls()
        filtered = display._filter_logs(all_logs)

        for log in filtered:
            assert log.log_type == BuildLogType.BUILDER_LIVE

    @pytest.mark.unit
    def test_filter_logs_by_chroot(self, sample_build: Build) -> None:
        """Test _filter_logs by chroot."""
        display = LogDisplay(chroots=["fedora-43-x86_64"])
        all_logs = sample_build.get_all_log_urls()
        filtered = display._filter_logs(all_logs)

        for log in filtered:
            if log.source == LogSource.RPM:
                assert log.chroot == "fedora-43-x86_64"

    @pytest.mark.unit
    def test_format_log_header_import(self, sample_import_log: BuildLog) -> None:
        """Test _format_log_header for import log."""
        display = LogDisplay()
        header = display._format_log_header(sample_import_log)

        assert isinstance(header, Text)
        header_str = str(header)
        assert "Import" in header_str or "📥" in header_str

    @pytest.mark.unit
    def test_format_log_header_srpm(self, sample_build_log: BuildLog) -> None:
        """Test _format_log_header for SRPM log."""
        display = LogDisplay()
        header = display._format_log_header(sample_build_log)

        assert isinstance(header, Text)
        header_str = str(header)
        assert "SRPM" in header_str or "📦" in header_str

    @pytest.mark.unit
    def test_format_log_header_rpm(self, sample_rpm_log: BuildLog) -> None:
        """Test _format_log_header for RPM log."""
        display = LogDisplay()
        header = display._format_log_header(sample_rpm_log)

        assert isinstance(header, Text)
        header_str = str(header)
        assert "fedora-43-x86_64" in header_str or "🔧" in header_str

    @pytest.mark.unit
    def test_format_log_header_live(self) -> None:
        """Test _format_log_header shows LIVE indicator."""
        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.BUILDER_LIVE,
            source=LogSource.SRPM,
            url="http://example.com/log",
            is_live=True,
        )
        display = LogDisplay()
        header = display._format_log_header(log)

        header_str = str(header)
        assert "LIVE" in header_str

    @pytest.mark.unit
    def test_on_chunk(self, mocker: MockerFixture, sample_build_log: BuildLog) -> None:
        """Test _on_chunk method."""
        console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=console)

        chunk = LogChunk(log=sample_build_log, content="line 1\nline 2")
        display._on_chunk(chunk)

        # Should print header and content lines
        assert console.print.call_count >= 3  # header + 2 lines

    @pytest.mark.unit
    def test_on_chunk_existing_log(
        self, mocker: MockerFixture, sample_build_log: BuildLog
    ) -> None:
        """Test _on_chunk for existing log (no header)."""
        console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=console)

        # Pre-populate log content
        display._log_content[sample_build_log.url] = ["previous"]

        chunk = LogChunk(log=sample_build_log, content="new line")
        display._on_chunk(chunk)

        # Should only print content, not header
        assert display._log_content[sample_build_log.url] == ["previous", "new line"]


class TestPrintBuildSummary:
    """Tests for print_build_summary function."""

    @pytest.mark.unit
    def test_print_build_summary(
        self, mocker: MockerFixture, sample_build: Build
    ) -> None:
        """Test print_build_summary function."""
        console = mocker.MagicMock(spec=Console)
        print_build_summary(sample_build, console)

        console.print.assert_called_once()

    @pytest.mark.unit
    def test_print_build_summary_no_console(
        self, mocker: MockerFixture, sample_build: Build
    ) -> None:
        """Test print_build_summary creates console if not provided."""
        # Just ensure it doesn't raise
        mocker.patch("fuzzytail.ui.display.Console")
        print_build_summary(sample_build)


class TestListBuilds:
    """Tests for list_builds function."""

    @pytest.mark.unit
    def test_list_builds(self, mocker: MockerFixture, sample_build: Build) -> None:
        """Test list_builds function."""
        console = mocker.MagicMock(spec=Console)
        list_builds([sample_build], console)

        console.print.assert_called_once()

    @pytest.mark.unit
    def test_list_builds_multiple(
        self, mocker: MockerFixture, sample_build: Build, sample_build_running: Build
    ) -> None:
        """Test list_builds with multiple builds."""
        console = mocker.MagicMock(spec=Console)
        list_builds([sample_build, sample_build_running], console)

        console.print.assert_called_once()

    @pytest.mark.unit
    def test_list_builds_empty(self, mocker: MockerFixture) -> None:
        """Test list_builds with empty list."""
        console = mocker.MagicMock(spec=Console)
        list_builds([], console)

        # Should still print table (with no rows)
        console.print.assert_called_once()


class TestStreamBuild:
    """Tests for LogDisplay.stream_build method."""

    @pytest.mark.unit
    def test_stream_build_basic(
        self, mocker: MockerFixture, sample_build: Build
    ) -> None:
        """Test stream_build method with a completed build."""
        from fuzzytail.ui.display import LogDisplay

        mock_console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=mock_console)

        # Mock the dependencies
        mock_streamer_class = mocker.patch("fuzzytail.ui.display.LogStreamer")
        mock_copr_class = mocker.patch("fuzzytail.ui.display.CoprService")
        mocker.patch("fuzzytail.ui.display._interruptible_sleep")

        mock_streamer = mocker.MagicMock()
        mock_streamer.get_new_content.return_value = None
        mock_streamer.is_log_complete.return_value = True
        mock_streamer.__enter__ = mocker.MagicMock(return_value=mock_streamer)
        mock_streamer.__exit__ = mocker.MagicMock(return_value=None)
        mock_streamer_class.return_value = mock_streamer

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = sample_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        display.stream_build(sample_build)

        # Should print build panel and completion message
        assert mock_console.print.called

    @pytest.mark.unit
    def test_stream_build_discovers_new_logs(
        self, mocker: MockerFixture, sample_build: Build
    ) -> None:
        """Test stream_build discovers and streams new logs."""
        from fuzzytail.ui.display import LogDisplay
        from fuzzytail.services.logs import LogChunk

        mock_console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=mock_console)

        mock_streamer_class = mocker.patch("fuzzytail.ui.display.LogStreamer")
        mock_copr_class = mocker.patch("fuzzytail.ui.display.CoprService")
        mocker.patch("fuzzytail.ui.display._interruptible_sleep")

        call_count = [0]

        def mock_get_new_content(log):
            call_count[0] += 1
            if call_count[0] == 1:
                return LogChunk(log=log, content="log content")
            return None

        mock_streamer = mocker.MagicMock()
        mock_streamer.get_new_content.side_effect = mock_get_new_content
        mock_streamer.is_log_complete.return_value = True
        mock_streamer.__enter__ = mocker.MagicMock(return_value=mock_streamer)
        mock_streamer.__exit__ = mocker.MagicMock(return_value=None)
        mock_streamer_class.return_value = mock_streamer

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = sample_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        display.stream_build(sample_build)

        assert mock_console.print.called


class TestWatchProject:
    """Tests for LogDisplay.watch_project method."""

    @pytest.mark.unit
    def test_watch_project_finds_builds(self, mocker: MockerFixture) -> None:
        """Test watch_project finds and streams active builds."""
        from fuzzytail.ui.display import LogDisplay
        from fuzzytail.models import Build, BuildState

        mock_console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=mock_console)

        mock_copr_class = mocker.patch("fuzzytail.ui.display.CoprService")
        mocker.patch("fuzzytail.ui.display._interruptible_sleep")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            package_name="testpackage",
            state=BuildState.RUNNING,
            chroots=[],
        )

        # Mock stream_build to raise KeyboardInterrupt to exit the loop
        def mock_stream_build(*args, **kwargs):
            raise KeyboardInterrupt()

        mocker.patch.object(display, "stream_build", side_effect=mock_stream_build)

        mock_copr = mocker.MagicMock()
        mock_copr.get_running_builds.return_value = [mock_build]
        mock_copr.get_pending_builds.return_value = []
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        try:
            display.watch_project("testowner", "testproject")
        except KeyboardInterrupt:
            pass

        assert mock_console.print.called

    @pytest.mark.unit
    def test_watch_project_filters_by_package(self, mocker: MockerFixture) -> None:
        """Test watch_project filters builds by package name."""
        from fuzzytail.ui.display import LogDisplay
        from fuzzytail.models import Build, BuildState

        mock_console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=mock_console)

        mock_copr_class = mocker.patch("fuzzytail.ui.display.CoprService")
        mocker.patch("fuzzytail.ui.display._interruptible_sleep")

        build1 = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            package_name="wanted-package",
            state=BuildState.RUNNING,
            chroots=[],
        )
        build2 = Build(
            id=12346,
            owner="testowner",
            project="testproject",
            package_name="other-package",
            state=BuildState.RUNNING,
            chroots=[],
        )

        # Mock stream_build to raise KeyboardInterrupt to exit the loop
        def mock_stream_build(*args, **kwargs):
            raise KeyboardInterrupt()

        mock_stream = mocker.patch.object(
            display, "stream_build", side_effect=mock_stream_build
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_running_builds.return_value = [build1, build2]
        mock_copr.get_pending_builds.return_value = []
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        try:
            display.watch_project("testowner", "testproject", package="wanted-package")
        except KeyboardInterrupt:
            pass

        # Should only stream the wanted package
        assert mock_stream.call_count == 1
        call_args = mock_stream.call_args[0]
        assert call_args[0].package_name == "wanted-package"

    @pytest.mark.unit
    def test_watch_project_handles_errors(self, mocker: MockerFixture) -> None:
        """Test watch_project handles errors gracefully."""
        from fuzzytail.ui.display import LogDisplay

        mock_console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=mock_console)

        mock_copr_class = mocker.patch("fuzzytail.ui.display.CoprService")
        mocker.patch("fuzzytail.ui.display._interruptible_sleep")

        call_count = [0]

        def mock_running(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API Error")
            raise KeyboardInterrupt()

        mock_copr = mocker.MagicMock()
        mock_copr.get_running_builds.side_effect = mock_running
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        try:
            display.watch_project("testowner", "testproject")
        except KeyboardInterrupt:
            pass

        # Should print error message
        assert any("Error" in str(call) for call in mock_console.print.call_args_list)

    @pytest.mark.unit
    def test_watch_project_no_active_builds(self, mocker: MockerFixture) -> None:
        """Test watch_project when no active builds."""
        from fuzzytail.ui.display import LogDisplay

        mock_console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=mock_console)

        mock_copr_class = mocker.patch("fuzzytail.ui.display.CoprService")
        mocker.patch("fuzzytail.ui.display._interruptible_sleep")

        call_count = [0]

        def mock_running(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return []
            raise KeyboardInterrupt()

        mock_copr = mocker.MagicMock()
        mock_copr.get_running_builds.side_effect = mock_running
        mock_copr.get_pending_builds.return_value = []
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        try:
            display.watch_project("testowner", "testproject")
        except KeyboardInterrupt:
            pass

        # Should print "waiting" message
        assert any(
            "Waiting" in str(call) or "No active" in str(call)
            for call in mock_console.print.call_args_list
        )


class TestInterruptibleSleepDisplay:
    """Tests for _interruptible_sleep in display module."""

    @pytest.mark.unit
    def test_interruptible_sleep_display(self) -> None:
        """Test _interruptible_sleep in display module."""
        from fuzzytail.ui.display import _interruptible_sleep
        import time

        start = time.time()
        _interruptible_sleep(0.2, interval=0.05)
        elapsed = time.time() - start

        assert 0.15 < elapsed < 0.4


class TestStreamBuildWithRefresh:
    """Tests for _stream_build_with_refresh method."""

    @pytest.mark.unit
    def test_stream_build_with_refresh_handles_exception(
        self, mocker: MockerFixture, sample_build: Build
    ) -> None:
        """Test _stream_build_with_refresh handles exceptions during refresh."""
        from fuzzytail.ui.display import LogDisplay

        mock_console = mocker.MagicMock(spec=Console)
        display = LogDisplay(console=mock_console)
        mocker.patch("fuzzytail.ui.display._interruptible_sleep")

        mock_streamer = mocker.MagicMock()
        mock_streamer.get_new_content.return_value = None
        mock_streamer.is_log_complete.return_value = True

        mock_copr = mocker.MagicMock()
        # First call succeeds, second raises exception
        mock_copr.get_build.side_effect = [sample_build, Exception("Refresh failed")]

        # This should not raise, just continue with cached build
        display._stream_build_with_refresh(sample_build, mock_copr, mock_streamer, 0.01)
