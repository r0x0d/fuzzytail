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
