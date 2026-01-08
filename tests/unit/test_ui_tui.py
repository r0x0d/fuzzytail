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
