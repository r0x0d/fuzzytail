"""Unit tests for fuzzytail Textual TUI."""

import pytest
from rich.text import Text

from fuzzytail.models import (
    Build,
    BuildChroot,
    BuildLog,
    BuildLogType,
    BuildState,
    LogSource,
)
from fuzzytail.ui.tui import BuildTUI, ChunkReceived, LogPanel


class TestLogPanel:
    """Tests for the LogPanel widget."""

    @pytest.mark.unit
    def test_make_title_live(self) -> None:
        """Title should show LIVE status when is_live is True."""
        panel = LogPanel(panel_key="SRPM", title="SRPM")
        panel.is_live = True
        panel.line_count = 42
        title = panel._make_title()
        assert "SRPM" in title
        assert "LIVE" in title
        assert "42" in title

    @pytest.mark.unit
    def test_make_title_done(self) -> None:
        """Title should show DONE status when is_live is False."""
        panel = LogPanel(panel_key="SRPM", title="SRPM")
        panel.is_live = False
        panel.line_count = 10
        title = panel._make_title()
        assert "DONE" in title
        assert "10" in title

    @pytest.mark.unit
    def test_make_title_minimized(self) -> None:
        """Title should show minimized hint when is_minimized is True."""
        panel = LogPanel(panel_key="SRPM", title="SRPM")
        panel.is_minimized = True
        title = panel._make_title()
        assert "minimized" in title

    @pytest.mark.unit
    def test_make_title_not_minimized(self) -> None:
        """Title should NOT show minimized hint when is_minimized is False."""
        panel = LogPanel(panel_key="SRPM", title="SRPM")
        panel.is_minimized = False
        title = panel._make_title()
        assert "minimized" not in title

    @pytest.mark.unit
    def test_max_lines_default(self) -> None:
        """LogPanel should default to MAX_LOG_LINES."""
        panel = LogPanel(panel_key="SRPM", title="SRPM")
        assert panel._max_lines == LogPanel.MAX_LOG_LINES

    @pytest.mark.unit
    def test_max_lines_custom(self) -> None:
        """LogPanel should accept a custom max_lines."""
        panel = LogPanel(panel_key="SRPM", title="SRPM", max_lines=500)
        assert panel._max_lines == 500


class TestBuildTUIHelpers:
    """Tests for BuildTUI class helper methods."""

    @pytest.mark.unit
    def test_chroot_key_import(self) -> None:
        """Import logs should produce 'IMPORT' key."""
        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.BACKEND,
            source=LogSource.IMPORT,
            url="http://example.com/import.log",
        )
        assert BuildTUI._chroot_key(log) == "IMPORT"

    @pytest.mark.unit
    def test_chroot_key_srpm(self) -> None:
        """SRPM logs should produce 'SRPM' key."""
        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.BUILDER_LIVE,
            source=LogSource.SRPM,
            url="http://example.com/srpm.log",
        )
        assert BuildTUI._chroot_key(log) == "SRPM"

    @pytest.mark.unit
    def test_chroot_key_rpm(self) -> None:
        """RPM logs should use the chroot name as key."""
        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.BUILDER_LIVE,
            source=LogSource.RPM,
            chroot="fedora-43-x86_64",
            url="http://example.com/rpm.log",
        )
        assert BuildTUI._chroot_key(log) == "fedora-43-x86_64"

    @pytest.mark.unit
    def test_chroot_title_import(self) -> None:
        """Import key should produce readable title."""
        assert "Import" in BuildTUI._chroot_title("IMPORT")

    @pytest.mark.unit
    def test_chroot_title_srpm(self) -> None:
        """SRPM key should produce readable title."""
        assert "SRPM" in BuildTUI._chroot_title("SRPM")

    @pytest.mark.unit
    def test_chroot_title_chroot(self) -> None:
        """Chroot key should appear in title."""
        assert "f43-x86_64" in BuildTUI._chroot_title("f43-x86_64")

    @pytest.mark.unit
    def test_parse_lines_plain(self) -> None:
        """Plain text should be parsed into Text objects."""
        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            )
        )
        lines = tui._parse_lines("hello\nworld\n")
        assert len(lines) == 2
        assert isinstance(lines[0], Text)
        assert str(lines[0]) == "hello"
        assert str(lines[1]) == "world"

    @pytest.mark.unit
    def test_parse_lines_ansi(self) -> None:
        """ANSI escape sequences should be preserved as Rich styles."""
        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            )
        )
        ansi_line = "\x1b[31mERROR\x1b[0m: something failed"
        lines = tui._parse_lines(ansi_line)
        assert len(lines) == 1
        assert "ERROR" in str(lines[0])

    @pytest.mark.unit
    def test_parse_lines_grep_filter(self) -> None:
        """Lines not matching grep pattern should be filtered out."""
        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            ),
            grep_pattern="error",
        )
        lines = tui._parse_lines("INFO: ok\nERROR: bad\nDEBUG: trace\n")
        assert len(lines) == 1
        assert "ERROR" in str(lines[0])

    @pytest.mark.unit
    def test_filter_logs(self) -> None:
        """Test that _filter_logs applies source filters correctly."""
        build = Build(
            id=1,
            owner="o",
            project="p",
            state=BuildState.RUNNING,
            chroots=[
                BuildChroot(
                    name="f43-x86_64",
                    state=BuildState.RUNNING,
                    result_url="https://example.com/f43",
                )
            ],
        )
        tui = BuildTUI(build=build, show_import=False, show_srpm=True, show_rpm=False)
        all_logs = build.get_all_log_urls()
        filtered = tui._filter_logs(all_logs)

        for log in filtered:
            assert log.source == LogSource.SRPM

    @pytest.mark.unit
    def test_parse_lines_search_highlight(self) -> None:
        """Lines matching _search_pattern should be highlighted."""
        import re

        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            )
        )
        tui._search_pattern = re.compile("error", re.IGNORECASE)
        lines = tui._parse_lines("INFO: ok\nERROR: bad\n")
        assert len(lines) == 2
        # The line with ERROR should have style spans applied
        error_line = lines[1]
        assert "ERROR" in str(error_line)
        # Check that the Text object has at least one style span
        assert len(error_line._spans) > 0


class TestLogColorization:
    """Tests for log-level-aware colorization of plain-text lines."""

    def _build_tui(self) -> BuildTUI:
        return BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            )
        )

    @pytest.mark.unit
    def test_error_line_gets_styled(self) -> None:
        """Plain-text error lines should receive red styling."""
        tui = self._build_tui()
        lines = tui._parse_lines("error: something broke\n")
        assert len(lines) == 1
        assert len(lines[0]._spans) > 0

    @pytest.mark.unit
    def test_warning_line_gets_styled(self) -> None:
        """Plain-text warning lines should receive yellow styling."""
        tui = self._build_tui()
        lines = tui._parse_lines("warning: this is deprecated\n")
        assert len(lines) == 1
        assert len(lines[0]._spans) > 0

    @pytest.mark.unit
    def test_shell_trace_gets_styled(self) -> None:
        """Shell trace (+ cmd) lines should receive cyan styling."""
        tui = self._build_tui()
        lines = tui._parse_lines("+ make -j4\n")
        assert len(lines) == 1
        assert len(lines[0]._spans) > 0

    @pytest.mark.unit
    def test_rpm_phase_gets_styled(self) -> None:
        """RPM build phase lines should receive styling."""
        tui = self._build_tui()
        lines = tui._parse_lines("Executing(%build): /bin/sh -e\n")
        assert len(lines) == 1
        assert len(lines[0]._spans) > 0

    @pytest.mark.unit
    def test_ansi_lines_keep_original_style(self) -> None:
        """Lines with ANSI codes should NOT be re-colorized."""
        tui = self._build_tui()
        ansi_line = "\x1b[32mGreen text\x1b[0m"
        lines = tui._parse_lines(ansi_line)
        assert len(lines) == 1
        # The spans should come from ANSI parsing, not our colorizer
        assert len(lines[0]._spans) > 0

    @pytest.mark.unit
    def test_plain_generic_line_no_extra_style(self) -> None:
        """A generic plain-text line not matching any pattern stays unstyled."""
        tui = self._build_tui()
        lines = tui._parse_lines("gcc -c -o foo.o foo.c\n")
        assert len(lines) == 1
        # No pattern matches, so no styles added
        assert len(lines[0]._spans) == 0

    @pytest.mark.unit
    def test_make_error_gets_styled(self) -> None:
        """make *** error lines should get styled as errors."""
        tui = self._build_tui()
        lines = tui._parse_lines("make[2]: *** [Makefile:42: all] Error 2\n")
        assert len(lines) == 1
        assert len(lines[0]._spans) > 0

    @pytest.mark.unit
    def test_timestamp_gets_styled(self) -> None:
        """Timestamp-prefixed lines should get dim styling."""
        tui = self._build_tui()
        lines = tui._parse_lines("2025-01-15 12:30:45 INFO Starting build\n")
        assert len(lines) == 1
        assert len(lines[0]._spans) > 0


class TestChunkReceivedMessage:
    """Tests for ChunkReceived message."""

    @pytest.mark.unit
    def test_chunk_received_attributes(self) -> None:
        """ChunkReceived should carry key, title, and lines."""
        lines = [Text("hello"), Text("world")]
        msg = ChunkReceived(key="SRPM", title="SRPM", lines=lines)
        assert msg.key == "SRPM"
        assert msg.title == "SRPM"
        assert len(msg.lines) == 2


class TestBuildTUIInit:
    """Tests for BuildTUI initialization."""

    @pytest.mark.unit
    def test_init_with_build(self) -> None:
        """BuildTUI should accept a build for single-build streaming."""
        build = Build(
            id=42,
            owner="testowner",
            project="testproject",
            state=BuildState.RUNNING,
            chroots=[],
        )
        tui = BuildTUI(build=build)
        assert tui._build is build
        assert tui._owner is None

    @pytest.mark.unit
    def test_init_with_project(self) -> None:
        """BuildTUI should accept owner/project for watch mode."""
        tui = BuildTUI(owner="testowner", project="testproject", package="pkg")
        assert tui._build is None
        assert tui._owner == "testowner"
        assert tui._project == "testproject"
        assert tui._package == "pkg"

    @pytest.mark.unit
    def test_init_grep_pattern(self) -> None:
        """BuildTUI should compile a grep pattern."""
        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            ),
            grep_pattern="error|warning",
        )
        assert tui._grep is not None
        assert tui._grep.search("this is an error")
        assert not tui._grep.search("all good")

    @pytest.mark.unit
    def test_init_invalid_grep_pattern(self) -> None:
        """BuildTUI should escape invalid regex patterns."""
        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            ),
            grep_pattern="[invalid",
        )
        # Should not raise, pattern is escaped
        assert tui._grep is not None
        assert tui._grep.search("[invalid")

    @pytest.mark.unit
    def test_init_selected_log_none(self) -> None:
        """BuildTUI should start with no selected log (show all)."""
        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            )
        )
        assert tui._selected_log is None

    @pytest.mark.unit
    def test_init_search_pattern_none(self) -> None:
        """BuildTUI should start with no search pattern."""
        tui = BuildTUI(
            build=Build(
                id=1,
                owner="o",
                project="p",
                state=BuildState.RUNNING,
                chroots=[],
            )
        )
        assert tui._search_pattern is None
        assert tui._search_visible is False
