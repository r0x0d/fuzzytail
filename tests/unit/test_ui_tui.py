"""Unit tests for the TUI components."""

import re
from unittest.mock import MagicMock

from rich.text import Text

from fuzzytail.models import BuildLogType


class TestLogView:
    """Tests for the LogView widget."""

    def test_add_line_stores_content(self):
        """Test that add_line stores content in internal list."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()  # Mock the write method

        log_view.add_line("test line 1")
        log_view.add_line("test line 2")

        assert log_view._lines == ["test line 1", "test line 2"]
        assert log_view.write.call_count == 2

    def test_set_search_pattern_valid_regex(self):
        """Test setting a valid regex pattern."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view._lines = [
            "error: something failed",
            "info: all good",
            "error: another issue",
        ]
        log_view._raw_lines = [
            "error: something failed",
            "info: all good",
            "error: another issue",
        ]
        log_view.set_search_pattern("error")

        assert log_view._search_pattern is not None
        assert log_view.match_count == 2

    def test_set_search_pattern_invalid_regex_fallback(self):
        """Test that invalid regex falls back to literal search."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view._lines = ["test [bracket", "another line"]
        log_view._raw_lines = ["test [bracket", "another line"]
        # Invalid regex with unclosed bracket - should fall back to literal
        log_view.set_search_pattern("[bracket")

        assert log_view._search_pattern is not None
        assert log_view.match_count == 1

    def test_set_search_pattern_case_insensitive(self):
        """Test that search is case insensitive."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view._lines = ["ERROR: failed", "Error: warning", "error: info"]
        log_view._raw_lines = ["ERROR: failed", "Error: warning", "error: info"]
        log_view.set_search_pattern("error")

        assert log_view.match_count == 3

    def test_next_match_cycles(self):
        """Test that next_match cycles through matches."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view._lines = ["match1", "match2", "match3"]
        log_view._raw_lines = ["match1", "match2", "match3"]
        log_view.set_search_pattern("match")

        assert log_view.current_match == 1

        log_view.next_match()
        assert log_view.current_match == 2

        log_view.next_match()
        assert log_view.current_match == 3

        log_view.next_match()
        assert log_view.current_match == 1  # Cycles back

    def test_prev_match_cycles(self):
        """Test that prev_match cycles through matches."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view._lines = ["match1", "match2", "match3"]
        log_view._raw_lines = ["match1", "match2", "match3"]
        log_view.set_search_pattern("match")

        assert log_view.current_match == 1

        log_view.prev_match()
        assert log_view.current_match == 3  # Goes to last

        log_view.prev_match()
        assert log_view.current_match == 2

    def test_clear_search(self):
        """Test clearing the search pattern."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view._lines = ["test line"]
        log_view._raw_lines = ["test line"]
        log_view.set_search_pattern("test")
        assert log_view.match_count == 1

        log_view.clear_search()
        assert log_view._search_pattern is None
        assert log_view.match_count == 0

    def test_highlight_line(self):
        """Test that _highlight_line returns Rich Text with styling."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view._search_pattern = re.compile("error", re.IGNORECASE)

        text = log_view._highlight_line("This is an error message")

        assert isinstance(text, Text)
        # Check that the text has some styling applied
        assert len(text._spans) > 0

    def test_match_count_updates_with_new_lines(self):
        """Test that match count updates when new lines are added."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()

        log_view.set_search_pattern("error")
        assert log_view.match_count == 0

        log_view.add_line("error: line 1")
        assert log_view.match_count == 1

        log_view.add_line("info: line 2")
        assert log_view.match_count == 1

        log_view.add_line("error: line 3")
        assert log_view.match_count == 2

    def test_get_all_text(self):
        """Test that get_all_text returns all lines as string."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()

        log_view.add_line("line 1")
        log_view.add_line("line 2")
        log_view.add_line("line 3")

        result = log_view.get_all_text()
        assert result == "line 1\nline 2\nline 3"

    def test_get_matching_lines(self):
        """Test that get_matching_lines returns only matching lines."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view.add_line("error: first")
        log_view.add_line("info: second")
        log_view.add_line("error: third")
        log_view.add_line("debug: fourth")

        log_view.set_search_pattern("error")

        matching = log_view.get_matching_lines()
        assert len(matching) == 2
        assert matching[0] == "error: first"
        assert matching[1] == "error: third"

    def test_get_matching_text(self):
        """Test that get_matching_text returns matching lines as string."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view.add_line("error: first")
        log_view.add_line("info: second")
        log_view.add_line("error: third")

        log_view.set_search_pattern("error")

        result = log_view.get_matching_text()
        assert result == "error: first\nerror: third"

    def test_get_matching_lines_no_pattern(self):
        """Test that get_matching_lines returns empty when no search pattern."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()

        log_view.add_line("line 1")
        log_view.add_line("line 2")

        matching = log_view.get_matching_lines()
        assert matching == []

    def test_search_active_flag(self):
        """Test that _search_active flag is set correctly."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()
        log_view.scroll_to = MagicMock()

        log_view._lines = ["test line"]
        log_view._raw_lines = ["test line"]

        assert log_view._search_active is False

        log_view.set_search_pattern("test")
        assert log_view._search_active is True

        log_view.clear_search()
        assert log_view._search_active is False


class TestHelpBar:
    """Tests for the HelpBar widget."""

    def test_helpbar_creation(self):
        """Test that HelpBar can be created."""
        from fuzzytail.ui.tui import HelpBar

        help_bar = HelpBar()
        assert help_bar is not None


class TestSearchBar:
    """Tests for the SearchBar widget."""

    def test_show_adds_visible_class(self):
        """Test that show() adds the visible class."""
        from fuzzytail.ui.tui import SearchBar

        search_bar = SearchBar()
        # Mock the DOM methods
        search_bar.add_class = MagicMock()
        search_bar.query_one = MagicMock()

        search_bar.show()

        search_bar.add_class.assert_called_once_with("visible")

    def test_hide_removes_visible_class(self):
        """Test that hide() removes the visible class."""
        from fuzzytail.ui.tui import SearchBar

        search_bar = SearchBar()
        # Mock the DOM methods
        search_bar.remove_class = MagicMock()
        mock_input = MagicMock()
        mock_input.value = "test"
        search_bar.query_one = MagicMock(return_value=mock_input)

        search_bar.hide()

        search_bar.remove_class.assert_called_once_with("visible")
        assert mock_input.value == ""


class TestStatusBar:
    """Tests for the StatusBar widget."""

    def test_reactive_build_info(self):
        """Test that build_info reactive property works."""
        from fuzzytail.ui.tui import StatusBar

        status_bar = StatusBar()
        status_bar.build_info = "Build #123 - mypackage"

        assert status_bar.build_info == "Build #123 - mypackage"

    def test_reactive_search_info(self):
        """Test that search_info reactive property works."""
        from fuzzytail.ui.tui import StatusBar

        status_bar = StatusBar()
        status_bar.search_info = "Match 3/15"

        assert status_bar.search_info == "Match 3/15"


class TestFuzzytailApp:
    """Tests for the FuzzytailApp."""

    def test_app_initialization(self):
        """Test that app initializes with correct parameters."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(
            owner="testowner",
            project="testproject",
            package="testpackage",
            chroot="fedora-43-x86_64",
            show_import=False,
            show_srpm=True,
            show_rpm=True,
            log_types=[BuildLogType.BUILDER_LIVE],
            poll_interval=3.0,
        )

        assert app.owner == "testowner"
        assert app.project_name == "testproject"
        assert app.package == "testpackage"
        assert app.chroot == "fedora-43-x86_64"
        assert app.show_import is False
        assert app.show_srpm is True
        assert app.show_rpm is True
        assert app.log_types == [BuildLogType.BUILDER_LIVE]
        assert app.chroots == ["fedora-43-x86_64"]
        assert app.poll_interval == 3.0

    def test_app_initialization_no_chroot(self):
        """Test that app handles None chroot correctly."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(
            owner="testowner",
            project="testproject",
        )

        assert app.chroots is None

    def test_app_initialization_with_build_id(self):
        """Test that app initializes with build_id."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(
            owner="testowner",
            project="testproject",
            build_id=12345678,
        )

        assert app.build_id == 12345678

    def test_app_bindings(self):
        """Test that app has expected keybindings."""
        from fuzzytail.ui.tui import FuzzytailApp
        from textual.binding import Binding

        # Extract keys from bindings (can be Binding objects or tuples)
        binding_keys = []
        for b in FuzzytailApp.BINDINGS:
            if isinstance(b, Binding):
                binding_keys.append(b.key)
            else:
                binding_keys.append(b[0])  # First element of tuple is the key

        assert "q" in binding_keys
        assert "slash" in binding_keys
        assert "n" in binding_keys
        assert "N" in binding_keys
        assert "escape" in binding_keys
        assert "y" in binding_keys  # Copy binding
        assert "ctrl+c" in binding_keys

    def test_app_has_mouse_support(self):
        """Test that app has mouse support enabled."""
        from fuzzytail.ui.tui import FuzzytailApp

        assert FuzzytailApp.MOUSE_SUPPORT is True

    def test_app_ansi_color_enabled(self):
        """Test that app uses ANSI colors from terminal."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        # The ansi_color parameter is passed to the App constructor
        assert app.ansi_color is True

    def test_interruptible_sleep_respects_stop(self):
        """Test that _interruptible_sleep respects stop flag."""
        from fuzzytail.ui.tui import FuzzytailApp
        import time

        app = FuzzytailApp(owner="test", project="test")
        app._stop = True

        start = time.time()
        app._interruptible_sleep(5.0)  # Should return immediately
        elapsed = time.time() - start

        assert elapsed < 1.0  # Should be much less than 5 seconds

    def test_filter_logs(self):
        """Test _filter_logs method."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import BuildLog, BuildLogType, LogSource

        app = FuzzytailApp(
            owner="test",
            project="test",
            show_import=True,
            show_srpm=True,
            show_rpm=False,
        )

        logs = [
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BACKEND,
                source=LogSource.IMPORT,
                url="http://example.com/import.log",
            ),
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BACKEND,
                source=LogSource.SRPM,
                url="http://example.com/srpm.log",
            ),
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BACKEND,
                source=LogSource.RPM,
                chroot="fedora-43-x86_64",
                url="http://example.com/rpm.log",
            ),
        ]

        filtered = app._filter_logs(logs)

        # Should exclude RPM logs
        assert len(filtered) == 2
        assert all(log.source != LogSource.RPM for log in filtered)


class TestSearchBarProperties:
    """Additional tests for SearchBar widget."""

    def test_is_visible_property(self):
        """Test is_visible property."""
        from fuzzytail.ui.tui import SearchBar

        search_bar = SearchBar()
        search_bar.has_class = MagicMock(return_value=False)

        assert search_bar.is_visible is False

        search_bar.has_class.return_value = True
        assert search_bar.is_visible is True

    def test_value_property(self):
        """Test value property returns input value."""
        from fuzzytail.ui.tui import SearchBar

        search_bar = SearchBar()
        mock_input = MagicMock()
        mock_input.value = "search term"
        search_bar.query_one = MagicMock(return_value=mock_input)

        assert search_bar.value == "search term"


class TestLogViewEdgeCases:
    """Additional edge case tests for LogView."""

    def test_add_line_without_search_pattern(self):
        """Test add_line when no search pattern is set."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.scroll_end = MagicMock()

        log_view.add_line("simple line")

        assert len(log_view._lines) == 1
        assert len(log_view._raw_lines) == 1
        log_view.write.assert_called_once()

    def test_add_line_with_markup(self):
        """Test add_line handles Rich markup correctly."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.scroll_end = MagicMock()

        log_view.add_line("[bold]styled text[/bold]")

        assert len(log_view._raw_lines) == 1
        # Raw text should be without markup
        assert log_view._raw_lines[0] == "styled text"

    def test_add_line_with_invalid_markup(self):
        """Test add_line handles invalid markup gracefully."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.scroll_end = MagicMock()

        # Invalid markup - should not crash
        log_view.add_line("[unclosed bracket")

        assert len(log_view._lines) == 1

    def test_highlight_line_without_pattern(self):
        """Test _highlight_line when no pattern is set."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view._search_pattern = None

        text = log_view._highlight_line("test line")

        assert isinstance(text, Text)

    def test_scroll_to_match_out_of_bounds(self):
        """Test _scroll_to_match with out of bounds index."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.scroll_to = MagicMock()
        log_view._match_positions = [(0, 0, 4)]

        # Should not crash with invalid index
        log_view._scroll_to_match(-1)
        log_view._scroll_to_match(100)

    def test_next_match_no_matches(self):
        """Test next_match with no matches."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.scroll_to = MagicMock()
        log_view._match_positions = []

        # Should not crash
        log_view.next_match()
        assert log_view._current_match_idx == -1

    def test_prev_match_no_matches(self):
        """Test prev_match with no matches."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.scroll_to = MagicMock()
        log_view._match_positions = []

        # Should not crash
        log_view.prev_match()
        assert log_view._current_match_idx == -1

    def test_current_match_property(self):
        """Test current_match property."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view._current_match_idx = -1

        assert log_view.current_match == 0

        log_view._current_match_idx = 2
        assert log_view.current_match == 3  # 1-based


class TestStatusBarWatchers:
    """Tests for StatusBar watch methods."""

    def test_watch_build_info_handles_exception(self):
        """Test watch_build_info handles exceptions."""
        from fuzzytail.ui.tui import StatusBar

        status_bar = StatusBar()
        # query_one will fail since widget is not mounted
        status_bar.query_one = MagicMock(side_effect=Exception("Not mounted"))

        # Should not raise
        status_bar.watch_build_info("test info")

    def test_watch_search_info_handles_exception(self):
        """Test watch_search_info handles exceptions."""
        from fuzzytail.ui.tui import StatusBar

        status_bar = StatusBar()
        status_bar.query_one = MagicMock(side_effect=Exception("Not mounted"))

        # Should not raise
        status_bar.watch_search_info("test search info")


class TestHasPyperclip:
    """Tests for pyperclip availability."""

    def test_has_pyperclip_constant(self):
        """Test HAS_PYPERCLIP constant is defined."""
        from fuzzytail.ui import tui

        # Should be defined as boolean
        assert isinstance(tui.HAS_PYPERCLIP, bool)


class TestLogViewRefreshDisplay:
    """Tests for LogView._refresh_display method."""

    def test_refresh_display_with_pattern(self):
        """Test _refresh_display with search pattern."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()

        log_view._lines = ["error: test", "info: test"]
        log_view._search_pattern = re.compile("error", re.IGNORECASE)

        log_view._refresh_display()

        assert log_view.clear.called
        assert log_view.write.call_count == 2

    def test_refresh_display_without_pattern(self):
        """Test _refresh_display without search pattern."""
        from fuzzytail.ui.tui import LogView

        log_view = LogView()
        log_view.write = MagicMock()
        log_view.clear = MagicMock()

        log_view._lines = ["line 1", "line 2"]
        log_view._search_pattern = None

        log_view._refresh_display()

        assert log_view.clear.called
        assert log_view.write.call_count == 2


class TestFuzzytailAppMethods:
    """Tests for FuzzytailApp methods."""

    def test_add_log_header_import(self):
        """Test _add_log_header for import log."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import BuildLog, BuildLogType, LogSource

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.IMPORT,
            source=LogSource.IMPORT,
            url="http://example.com/import.log",
        )

        app._add_log_header(log)

        # Should call _add_log_lines via call_from_thread
        assert app.call_from_thread.called

    def test_add_log_header_srpm(self):
        """Test _add_log_header for SRPM log."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import BuildLog, BuildLogType, LogSource

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.BUILDER_LIVE,
            source=LogSource.SRPM,
            url="http://example.com/srpm.log",
            is_live=True,
        )

        app._add_log_header(log)

        assert app.call_from_thread.called

    def test_add_log_header_rpm(self):
        """Test _add_log_header for RPM log."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import BuildLog, BuildLogType, LogSource

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.BACKEND,
            source=LogSource.RPM,
            chroot="fedora-43-x86_64",
            url="http://example.com/rpm.log",
            is_live=True,
        )

        app._add_log_header(log)

        assert app.call_from_thread.called

    def test_on_chunk(self):
        """Test _on_chunk method."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import BuildLog, BuildLogType, LogSource
        from fuzzytail.services.logs import LogChunk

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        log = BuildLog(
            build_id=1,
            log_type=BuildLogType.BACKEND,
            source=LogSource.SRPM,
            url="http://example.com/log",
        )
        chunk = LogChunk(log=log, content="line 1\nline 2\nline 3")

        app._on_chunk(chunk)

        assert app.call_from_thread.called

    def test_add_log_line(self):
        """Test _add_log_line method."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        app._add_log_line("single line")

        assert app.call_from_thread.called

    def test_add_log_lines(self):
        """Test _add_log_lines method."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        app._add_log_lines(["line 1", "line 2"])

        assert app.call_from_thread.called

    def test_add_log_lines_empty(self):
        """Test _add_log_lines with empty list."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        app._add_log_lines([])

        # Should not call anything for empty list
        assert not app.call_from_thread.called

    def test_update_status(self):
        """Test _update_status method."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()

        app._update_status("Build #123")

        assert app.call_from_thread.called


class TestSearchBarCompose:
    """Tests for SearchBar compose method."""

    def test_compose_yields_widgets(self):
        """Test that compose yields expected widgets."""
        from fuzzytail.ui.tui import SearchBar

        search_bar = SearchBar()
        widgets = list(search_bar.compose())

        assert len(widgets) == 2  # Static label and Input


class TestHelpBarCompose:
    """Tests for HelpBar compose method."""

    def test_compose_yields_widgets(self):
        """Test that compose yields expected widgets."""
        from fuzzytail.ui.tui import HelpBar

        help_bar = HelpBar()
        widgets = list(help_bar.compose())

        assert len(widgets) == 1  # Static with help text


class TestStatusBarCompose:
    """Tests for StatusBar compose method."""

    def test_compose_yields_widgets(self):
        """Test that compose yields expected widgets."""
        from fuzzytail.ui.tui import StatusBar

        status_bar = StatusBar()
        widgets = list(status_bar.compose())

        assert len(widgets) == 2  # Left and right status


class TestFuzzytailAppCompose:
    """Tests for FuzzytailApp compose method."""

    def test_compose_yields_widgets(self):
        """Test that compose yields expected widgets."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        widgets = list(app.compose())

        assert len(widgets) == 4  # Container, StatusBar, HelpBar, SearchBar


class TestFuzzytailAppStreaming:
    """Tests for FuzzytailApp streaming methods."""

    def test_stream_single_build(self, mocker):
        """Test _stream_single_build method."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import Build, BuildState

        app = FuzzytailApp(owner="test", project="test", build_id=12345)
        app.call_from_thread = MagicMock()

        mock_copr_class = mocker.patch("fuzzytail.ui.tui.CoprService")

        mock_build = Build(
            id=12345,
            owner="test",
            project="test",
            package_name="testpkg",
            state=BuildState.SUCCEEDED,
            chroots=[],
        )

        mock_copr = MagicMock()
        mock_copr.get_build.return_value = mock_build
        mock_copr.__enter__ = MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        # Mock _stream_build_logs to avoid full execution
        mocker.patch.object(app, "_stream_build_logs")

        app._stream_single_build()

        mock_copr.get_build.assert_called_once_with(12345)

    def test_watch_project_finds_new_builds(self, mocker):
        """Test _watch_project finds and streams new builds."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import Build, BuildState

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()
        app._stop = False

        mock_copr_class = mocker.patch("fuzzytail.ui.tui.CoprService")

        mock_build = Build(
            id=12345,
            owner="test",
            project="test",
            package_name="testpkg",
            state=BuildState.RUNNING,
            chroots=[],
        )

        call_count = [0]

        def mock_running(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [mock_build]
            app._stop = True
            return []

        mock_copr = MagicMock()
        mock_copr.get_running_builds.side_effect = mock_running
        mock_copr.get_pending_builds.return_value = []
        mock_copr.__enter__ = MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        # Mock _stream_build_logs
        mocker.patch.object(app, "_stream_build_logs")
        mocker.patch.object(app, "_interruptible_sleep")

        app._watch_project()

        assert app.call_from_thread.called

    def test_watch_project_filters_by_package(self, mocker):
        """Test _watch_project filters builds by package."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import Build, BuildState

        app = FuzzytailApp(owner="test", project="test", package="wanted")
        app.call_from_thread = MagicMock()
        app._stop = False

        mock_copr_class = mocker.patch("fuzzytail.ui.tui.CoprService")

        build1 = Build(
            id=12345,
            owner="test",
            project="test",
            package_name="wanted",
            state=BuildState.RUNNING,
            chroots=[],
        )
        build2 = Build(
            id=12346,
            owner="test",
            project="test",
            package_name="other",
            state=BuildState.RUNNING,
            chroots=[],
        )

        call_count = [0]

        def mock_running(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [build1, build2]
            app._stop = True
            return []

        mock_copr = MagicMock()
        mock_copr.get_running_builds.side_effect = mock_running
        mock_copr.get_pending_builds.return_value = []
        mock_copr.__enter__ = MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_stream = mocker.patch.object(app, "_stream_build_logs")
        mocker.patch.object(app, "_interruptible_sleep")

        app._watch_project()

        # Should only stream the wanted package
        assert mock_stream.call_count == 1

    def test_watch_project_handles_errors(self, mocker):
        """Test _watch_project handles errors gracefully."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()
        app._stop = False

        mock_copr_class = mocker.patch("fuzzytail.ui.tui.CoprService")

        call_count = [0]

        def mock_running(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("API Error")
            app._stop = True
            return []

        mock_copr = MagicMock()
        mock_copr.get_running_builds.side_effect = mock_running
        mock_copr.__enter__ = MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mocker.patch.object(app, "_interruptible_sleep")

        app._watch_project()

        # Should call add log line with error
        assert app.call_from_thread.called

    def test_watch_project_no_active_builds(self, mocker):
        """Test _watch_project when no active builds."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()
        app._stop = False

        mock_copr_class = mocker.patch("fuzzytail.ui.tui.CoprService")

        call_count = [0]

        def mock_running(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return []
            app._stop = True
            return []

        mock_copr = MagicMock()
        mock_copr.get_running_builds.side_effect = mock_running
        mock_copr.get_pending_builds.return_value = []
        mock_copr.__enter__ = MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mocker.patch.object(app, "_interruptible_sleep")

        app._watch_project()

        # Should update status
        assert app.call_from_thread.called


class TestFuzzytailAppStreamBuildLogs:
    """Tests for _stream_build_logs method."""

    def test_stream_build_logs_discovers_logs(self, mocker):
        """Test _stream_build_logs discovers and streams logs."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import Build, BuildState, BuildChroot

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()
        app._stop = False

        mock_streamer_class = mocker.patch("fuzzytail.ui.tui.LogStreamer")

        mock_build = Build(
            id=12345,
            owner="test",
            project="test",
            package_name="testpkg",
            state=BuildState.SUCCEEDED,
            chroots=[
                BuildChroot(
                    name="fedora-43-x86_64",
                    state=BuildState.SUCCEEDED,
                    result_url="http://example.com/results",
                )
            ],
        )

        mock_streamer = MagicMock()
        mock_streamer.get_new_content.return_value = None
        mock_streamer.is_log_complete.return_value = True
        mock_streamer.__enter__ = MagicMock(return_value=mock_streamer)
        mock_streamer.__exit__ = MagicMock(return_value=None)
        mock_streamer_class.return_value = mock_streamer

        mock_copr = MagicMock()
        mock_copr.get_build.return_value = mock_build

        mocker.patch.object(app, "_interruptible_sleep")

        app._stream_build_logs(mock_build, mock_copr)

        # Should have called call_from_thread for log discovery
        assert app.call_from_thread.called

    def test_stream_build_logs_respects_stop(self, mocker):
        """Test _stream_build_logs respects stop flag."""
        from fuzzytail.ui.tui import FuzzytailApp
        from fuzzytail.models import Build, BuildState

        app = FuzzytailApp(owner="test", project="test")
        app.call_from_thread = MagicMock()
        app._stop = True  # Already stopped

        mock_streamer_class = mocker.patch("fuzzytail.ui.tui.LogStreamer")

        mock_build = Build(
            id=12345,
            owner="test",
            project="test",
            state=BuildState.RUNNING,
            chroots=[],
        )

        mock_streamer = MagicMock()
        mock_streamer.__enter__ = MagicMock(return_value=mock_streamer)
        mock_streamer.__exit__ = MagicMock(return_value=None)
        mock_streamer_class.return_value = mock_streamer

        mock_copr = MagicMock()

        app._stream_build_logs(mock_build, mock_copr)

        # Should exit immediately due to stop flag


class TestFuzzytailAppActions:
    """Tests for FuzzytailApp action methods."""

    def test_action_open_search_shows_bar(self, mocker):
        """Test action_open_search shows search bar."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_search_bar = MagicMock()
        mock_search_bar.is_visible = False

        mock_log_view = MagicMock()
        mock_log_view._search_active = False

        app.query_one = MagicMock(
            side_effect=lambda x, cls: mock_search_bar
            if "search-bar" in x
            else mock_log_view
        )

        app.action_open_search()

        mock_search_bar.show.assert_called_once()

    def test_action_open_search_hides_visible_bar(self, mocker):
        """Test action_open_search hides visible search bar."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_search_bar = MagicMock()
        mock_search_bar.is_visible = True

        mock_log_view = MagicMock()
        mock_log_view._search_active = False
        mock_log_view._search_pattern = None
        mock_log_view.match_count = 0

        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "search-bar" in x:
                return mock_search_bar
            if "log-view" in x:
                return mock_log_view
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        app.action_open_search()

        mock_search_bar.hide.assert_called_once()
        mock_log_view.clear_search.assert_called_once()

    def test_action_close_search(self, mocker):
        """Test action_close_search method."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_search_bar = MagicMock()
        mock_search_bar.is_visible = True

        mock_log_view = MagicMock()

        app.query_one = MagicMock(
            side_effect=lambda x, cls: mock_search_bar
            if "search-bar" in x
            else mock_log_view
        )

        app.action_close_search()

        mock_search_bar.hide.assert_called_once()

    def test_action_close_search_clears_when_hidden(self, mocker):
        """Test action_close_search clears search when bar is hidden."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_search_bar = MagicMock()
        mock_search_bar.is_visible = False

        mock_log_view = MagicMock()
        mock_log_view._search_pattern = None
        mock_log_view.match_count = 0

        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "search-bar" in x:
                return mock_search_bar
            if "log-view" in x:
                return mock_log_view
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        app.action_close_search()

        mock_log_view.clear_search.assert_called_once()

    def test_action_next_match(self, mocker):
        """Test action_next_match method."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_log_view = MagicMock()
        mock_log_view._search_pattern = "test"
        mock_log_view.match_count = 5
        mock_log_view.current_match = 1

        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "log-view" in x:
                return mock_log_view
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        app.action_next_match()

        mock_log_view.next_match.assert_called_once()

    def test_action_prev_match(self, mocker):
        """Test action_prev_match method."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_log_view = MagicMock()
        mock_log_view._search_pattern = "test"
        mock_log_view.match_count = 5
        mock_log_view.current_match = 3

        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "log-view" in x:
                return mock_log_view
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        app.action_prev_match()

        mock_log_view.prev_match.assert_called_once()

    def test_update_search_info_with_matches(self, mocker):
        """Test _update_search_info with matches."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_log_view = MagicMock()
        mock_log_view._search_pattern = re.compile("test")
        mock_log_view.match_count = 5
        mock_log_view.current_match = 2

        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "log-view" in x:
                return mock_log_view
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        app._update_search_info()

        assert "Match 2/5" in mock_status_bar.search_info

    def test_update_search_info_no_matches(self, mocker):
        """Test _update_search_info with no matches."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_log_view = MagicMock()
        mock_log_view._search_pattern = re.compile("test")
        mock_log_view.match_count = 0

        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "log-view" in x:
                return mock_log_view
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        app._update_search_info()

        assert "No matches" in mock_status_bar.search_info

    def test_update_search_info_no_pattern(self, mocker):
        """Test _update_search_info with no search pattern."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_log_view = MagicMock()
        mock_log_view._search_pattern = None

        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "log-view" in x:
                return mock_log_view
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        app._update_search_info()

        assert mock_status_bar.search_info == ""

    def test_on_input_submitted(self, mocker):
        """Test on_input_submitted handler."""
        from fuzzytail.ui.tui import FuzzytailApp

        app = FuzzytailApp(owner="test", project="test")

        mock_log_view = MagicMock()
        mock_log_view._search_pattern = None
        mock_log_view.match_count = 0

        mock_search_bar = MagicMock()
        mock_status_bar = MagicMock()

        def query_side_effect(x, cls):
            if "log-view" in x:
                return mock_log_view
            if "search-bar" in x:
                return mock_search_bar
            return mock_status_bar

        app.query_one = MagicMock(side_effect=query_side_effect)

        # Create mock event
        mock_input = MagicMock()
        mock_input.id = "search-input"

        mock_event = MagicMock()
        mock_event.input = mock_input
        mock_event.value = "search term"

        app.on_input_submitted(mock_event)

        mock_log_view.set_search_pattern.assert_called_once_with("search term")
        mock_search_bar.hide.assert_called_once()
