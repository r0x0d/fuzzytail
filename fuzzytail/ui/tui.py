"""Interactive Textual TUI for streaming COPR build logs."""

from __future__ import annotations

import contextlib
import re
import time

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
)

from fuzzytail.models import Build, BuildLog, BuildLogType, LogSource
from fuzzytail.services.cache import LogCache
from fuzzytail.services.copr import CoprService
from fuzzytail.services.logs import LogChunk, LogStreamer
from fuzzytail.utils import filter_logs, format_elapsed, interruptible_sleep

# ---------------------------------------------------------------------------
# Custom messages for thread-safe communication from workers to UI
# ---------------------------------------------------------------------------


class ChunkReceived(Message):
    """A new log chunk arrived from the streaming worker."""

    def __init__(self, key: str, title: str, lines: list[Text]) -> None:
        super().__init__()
        self.key = key
        self.title = title
        self.lines = lines


class BuildInfoUpdated(Message):
    """Build metadata changed (state, elapsed, etc.)."""

    def __init__(self, info: str) -> None:
        super().__init__()
        self.info = info


class StreamingComplete(Message):
    """All logs have been fully streamed."""


# ---------------------------------------------------------------------------
# Per-column log panel widget
# ---------------------------------------------------------------------------

_PANEL_BORDER_STYLES = [
    "cyan",
    "green",
    "yellow",
    "magenta",
    "blue",
    "red",
    "bright_cyan",
    "bright_green",
    "bright_yellow",
]


class LogPanel(Static):
    """A titled, scrollable log panel for one column (SRPM / Import / chroot)."""

    line_count: reactive[int] = reactive(0)
    is_live: reactive[bool] = reactive(True)
    is_minimized: reactive[bool] = reactive(False)

    DEFAULT_CSS = """
    LogPanel {
        height: 1fr;
        width: 1fr;
        border: solid $accent;
        overflow: hidden;
    }
    LogPanel:focus-within {
        border: heavy $accent-lighten-2;
    }
    LogPanel.minimized {
        height: 3;
    }
    LogPanel.minimized RichLog {
        display: none;
    }
    LogPanel RichLog {
        height: 1fr;
        scrollbar-size-vertical: 1;
    }
    """

    MAX_LOG_LINES = 10_000

    def __init__(
        self,
        panel_key: str,
        title: str,
        border_style: str = "cyan",
        max_lines: int | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.panel_key = panel_key
        self._title = title
        self._border_style = border_style
        self._max_lines = max_lines if max_lines is not None else self.MAX_LOG_LINES
        self.border_title = self._make_title()
        self.styles.border = ("solid", border_style)

    def _make_title(self) -> str:
        if self.is_live:
            status = "[green]● LIVE[/green]"
        else:
            status = "[dim]○ DONE[/dim]"
        minimized_hint = (
            "  [dim italic]minimized[/dim italic]" if self.is_minimized else ""
        )
        return (
            f"[bold]{self._title}[/bold]"
            f"  {status}"
            f"  [dim]({self.line_count} lines)[/dim]"
            f"{minimized_hint}"
        )

    def compose(self) -> ComposeResult:
        yield RichLog(
            highlight=False,
            markup=False,
            auto_scroll=True,
            wrap=True,
            max_lines=self._max_lines,
            id=f"log-{self.panel_key}",
        )

    def watch_line_count(self) -> None:
        """Update title when line count changes."""
        self.border_title = self._make_title()

    def watch_is_live(self) -> None:
        """Update title when live status changes."""
        self.border_title = self._make_title()

    def watch_is_minimized(self, minimized: bool) -> None:
        """Toggle minimized CSS class and update title."""
        if minimized:
            self.add_class("minimized")
        else:
            self.remove_class("minimized")
        self.border_title = self._make_title()

    def append_lines(self, lines: list[Text]) -> None:
        """Append pre-parsed Rich Text lines to the log widget.

        Uses batch_update() to suppress per-line repaints, collapsing
        N render passes into a single repaint at the end.
        """
        rich_log = self.query_one(RichLog)
        with self.app.batch_update():
            for line in lines:
                rich_log.write(line)
        self.line_count += len(lines)

    @property
    def rich_log(self) -> RichLog:
        """Get the inner RichLog widget."""
        return self.query_one(RichLog)


# ---------------------------------------------------------------------------
# Status bar widget
# ---------------------------------------------------------------------------


class StatusBar(Static):
    """Top status bar showing build information."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    """

    def update_info(self, info: str) -> None:
        self.update(info)


# ---------------------------------------------------------------------------
# Sidebar log selector
# ---------------------------------------------------------------------------


class LogSidebarItem(ListItem):
    """A single entry in the log sidebar."""

    DEFAULT_CSS = """
    LogSidebarItem {
        height: 3;
        padding: 0 1;
    }
    LogSidebarItem:hover {
        background: $surface-lighten-1;
    }
    LogSidebarItem.-highlight {
        background: $primary-lighten-1;
    }
    """

    def __init__(self, key: str, title: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.log_key = key
        self._display_title = title

    def compose(self) -> ComposeResult:
        yield Label(self._display_title, id=f"sidebar-label-{self.log_key}")

    def update_label(self, text: str) -> None:
        """Update the displayed label text."""
        self._display_title = text
        try:
            label = self.query_one(f"#sidebar-label-{self.log_key}", Label)
            label.update(text)
        except Exception:
            pass


class LogSidebar(Static):
    """Left-hand sidebar listing all discovered log streams."""

    DEFAULT_CSS = """
    LogSidebar {
        width: 28;
        height: 1fr;
        border: solid $primary;
        border-title-color: $text;
        overflow-y: auto;
    }
    LogSidebar ListView {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield ListView(id="sidebar-list")

    def on_mount(self) -> None:
        self.border_title = "[bold]📋 Logs[/bold]"


# ---------------------------------------------------------------------------
# Search bar widget
# ---------------------------------------------------------------------------


class SearchBar(Static):
    """Bottom search input bar, toggled by `/`."""

    DEFAULT_CSS = """
    SearchBar {
        dock: bottom;
        height: 3;
        padding: 0 1;
        border: solid $accent;
        display: none;
    }
    SearchBar.visible {
        display: block;
    }
    SearchBar Input {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search logs (regex)…", id="search-input")


# ---------------------------------------------------------------------------
# Help overlay (modal screen)
# ---------------------------------------------------------------------------

_HELP_TEXT = """\
[bold cyan]fuzzytail — Keyboard Shortcuts[/bold cyan]

[bold]Navigation[/bold]
  [cyan]Tab[/cyan]          Next panel
  [cyan]Shift+Tab[/cyan]    Previous panel
  [cyan]1-9[/cyan]          Toggle panel visibility
  [cyan]b[/cyan]            Toggle sidebar
  [cyan]Enter[/cyan]        Select log in sidebar (focus single log)
  [cyan]Escape[/cyan]       Deselect / dismiss search / close help

[bold]Panel Control[/bold]
  [cyan]m[/cyan]            Minimize / restore focused panel
  [cyan]+[/cyan]            Grow focused panel width
  [cyan]-[/cyan]            Shrink focused panel width
  [cyan]=[/cyan]            Equalize all panel widths

[bold]View[/bold]
  [cyan]a[/cyan]            Toggle auto-scroll
  [cyan]/[/cyan]            Search in logs
  [cyan]?[/cyan]            Show this help

[bold]General[/bold]
  [cyan]q[/cyan]            Quit
"""


class HelpScreen(ModalScreen):
    """Modal overlay showing keybinding reference."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-container {
        width: 60;
        max-height: 80%;
        border: heavy $accent;
        background: $surface;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-container"):
            yield Static(_HELP_TEXT, id="help-text")

    def action_dismiss(self) -> None:
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# Main TUI application
# ---------------------------------------------------------------------------


class BuildTUI(App):
    """Interactive TUI for streaming COPR build logs.

    Provides scrollable, resizable, and toggleable log panels with
    ANSI color preservation, keyboard navigation, sidebar selection,
    in-log search, and a modern lazygit-inspired layout.
    """

    TITLE = "fuzzytail"

    CSS = """
    Screen {
        layout: vertical;
    }
    #main-area {
        height: 1fr;
        layout: horizontal;
    }
    #panel-container {
        height: 1fr;
        layout: horizontal;
    }
    #status-bar {
        dock: top;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("1", "toggle_panel('1')", "Toggle 1", show=False),
        Binding("2", "toggle_panel('2')", "Toggle 2", show=False),
        Binding("3", "toggle_panel('3')", "Toggle 3", show=False),
        Binding("4", "toggle_panel('4')", "Toggle 4", show=False),
        Binding("5", "toggle_panel('5')", "Toggle 5", show=False),
        Binding("6", "toggle_panel('6')", "Toggle 6", show=False),
        Binding("7", "toggle_panel('7')", "Toggle 7", show=False),
        Binding("8", "toggle_panel('8')", "Toggle 8", show=False),
        Binding("9", "toggle_panel('9')", "Toggle 9", show=False),
        Binding("equal_sign", "equalize", "Equalize"),
        Binding("plus,shift+equal_sign", "grow_panel", "Grow"),
        Binding("minus,hyphen_minus", "shrink_panel", "Shrink"),
        Binding("tab", "focus_next_panel", "Next panel", show=True),
        Binding("shift+tab", "focus_prev_panel", "Prev panel", show=False),
        Binding("a", "toggle_auto_scroll", "Auto-scroll"),
        Binding("b", "toggle_sidebar", "Sidebar"),
        Binding("m", "minimize_panel", "Minimize"),
        Binding("slash", "open_search", "Search"),
        Binding("question_mark", "show_help", "Help"),
        Binding("escape", "dismiss_overlays", "Dismiss", show=False),
    ]

    def __init__(
        self,
        build: Build | None = None,
        owner: str | None = None,
        project: str | None = None,
        package: str | None = None,
        *,
        show_import: bool = True,
        show_srpm: bool = True,
        show_rpm: bool = True,
        log_types: list[BuildLogType] | None = None,
        chroots: list[str] | None = None,
        grep_pattern: str | None = None,
        poll_interval: float = 2.0,
    ) -> None:
        super().__init__()
        # Either build (stream one build) or owner+project (watch mode)
        self._build = build
        self._owner = owner
        self._project = project
        self._package = package

        # Filter settings
        self._show_import = show_import
        self._show_srpm = show_srpm
        self._show_rpm = show_rpm
        self._log_types = log_types
        self._chroots = chroots
        self._poll_interval = poll_interval

        # Grep pattern
        self._grep: re.Pattern[str] | None = None
        if grep_pattern:
            try:
                self._grep = re.compile(grep_pattern, re.IGNORECASE)
            except re.error:
                self._grep = re.compile(re.escape(grep_pattern), re.IGNORECASE)

        # Panel tracking
        self._panels: dict[str, LogPanel] = {}
        self._panel_order: list[str] = []
        self._panel_sizes: dict[str, int] = {}  # key -> relative weight
        self._color_idx = 0
        self._auto_scroll = True

        # Sidebar selection state: None = show all, else show one log
        self._selected_log: str | None = None

        # Search state
        self._search_visible = False
        self._search_pattern: re.Pattern[str] | None = None

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatusBar(id="status-bar")
        with Horizontal(id="main-area"):
            yield LogSidebar(id="log-sidebar")
            yield Horizontal(id="panel-container")
        yield SearchBar(id="search-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Start streaming when the app mounts."""
        status = self.query_one("#status-bar", StatusBar)
        if self._build:
            pkg = self._build.package_name or "unknown"
            status.update_info(
                f"Build #{self._build.id} — "
                f"{self._build.owner}/{self._build.project} — {pkg}"
            )
            self.run_worker(self._stream_build_worker, thread=True)
        elif self._owner and self._project:
            status.update_info(
                f"Watching {self._owner}/{self._project}"
                + (f" (package: {self._package})" if self._package else "")
            )
            self.run_worker(self._watch_project_worker, thread=True)

    # ------------------------------------------------------------------
    # Panel management
    # ------------------------------------------------------------------

    def _next_color(self) -> str:
        color = _PANEL_BORDER_STYLES[self._color_idx % len(_PANEL_BORDER_STYLES)]
        self._color_idx += 1
        return color

    def _ensure_panel(self, key: str, title: str) -> None:
        """Create a panel if it doesn't already exist.

        Must be called on the main thread.
        """
        if key in self._panels:
            return

        color = self._next_color()
        panel = LogPanel(panel_key=key, title=title, border_style=color)
        self._panels[key] = panel
        self._panel_order.append(key)
        self._panel_sizes[key] = 1

        container = self.query_one("#panel-container", Horizontal)
        container.mount(panel)

        # Add to sidebar
        self._add_sidebar_item(key, title)

        self._reflow_panels()

    def _add_sidebar_item(self, key: str, title: str) -> None:
        """Add an entry to the log sidebar."""
        try:
            sidebar_list = self.query_one("#sidebar-list", ListView)
            item = LogSidebarItem(key=key, title=title, id=f"sb-{key}")
            sidebar_list.append(item)
        except Exception:
            pass

    def _update_sidebar_item(self, key: str) -> None:
        """Refresh the sidebar label for a given panel key."""
        if key not in self._panels:
            return
        panel = self._panels[key]
        status = "● LIVE" if panel.is_live else "○ DONE"
        text = f"{self._chroot_title(key)}  {status}  ({panel.line_count})"
        try:
            item = self.query_one(f"#sb-{key}", LogSidebarItem)
            item.update_label(text)
        except Exception:
            pass

    def _reflow_panels(self) -> None:
        """Recalculate panel widths based on weights and selection."""
        if self._selected_log is not None:
            # Single-log focus mode: show only the selected panel
            for key in self._panel_order:
                panel = self._panels[key]
                if key == self._selected_log:
                    panel.display = True
                    panel.styles.width = "1fr"
                else:
                    panel.display = False
            return

        # Default: show all non-hidden panels
        visible = [
            k for k in self._panel_order if not self._panels[k].has_class("user-hidden")
        ]
        if not visible:
            return
        total_weight = sum(self._panel_sizes[k] for k in visible)
        for key in self._panel_order:
            panel = self._panels[key]
            if key in visible:
                panel.display = True
                fraction = self._panel_sizes[key] / total_weight
                panel.styles.width = f"{fraction:.4f}fr"
            else:
                panel.display = False

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chroot_key(log: BuildLog) -> str:
        if log.source == LogSource.IMPORT:
            return "IMPORT"
        if log.source == LogSource.SRPM:
            return "SRPM"
        return log.chroot or "unknown"

    @staticmethod
    def _chroot_title(key: str) -> str:
        if key == "IMPORT":
            return "📥 Import"
        if key == "SRPM":
            return "📦 SRPM"
        return f"🔧 {key}"

    # ------------------------------------------------------------------
    # Message handlers (run on the main / UI thread)
    # ------------------------------------------------------------------

    def on_chunk_received(self, message: ChunkReceived) -> None:
        self._ensure_panel(message.key, message.title)
        self._panels[message.key].append_lines(message.lines)
        self._update_sidebar_item(message.key)

    def on_build_info_updated(self, message: BuildInfoUpdated) -> None:
        status = self.query_one("#status-bar", StatusBar)
        status.update_info(message.info)

    def on_streaming_complete(self, _message: StreamingComplete) -> None:
        # Mark all panels as done
        for panel in self._panels.values():
            panel.is_live = False
        # Update all sidebar items
        for key in self._panel_order:
            self._update_sidebar_item(key)
        status = self.query_one("#status-bar", StatusBar)
        current = str(status.renderable) if hasattr(status, "renderable") else ""
        status.update_info(f"{current}  [bold green]✓ All logs complete[/bold green]")

    # ------------------------------------------------------------------
    # Sidebar selection
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle sidebar item selection."""
        item = event.item
        if not isinstance(item, LogSidebarItem):
            return
        key = item.log_key
        if self._selected_log == key:
            # Deselect: go back to showing all
            self._selected_log = None
        else:
            self._selected_log = key
        self._reflow_panels()

    # ------------------------------------------------------------------
    # Search handling
    # ------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission."""
        if event.input.id != "search-input":
            return
        pattern_str = event.value.strip()
        if not pattern_str:
            self._search_pattern = None
        else:
            try:
                self._search_pattern = re.compile(pattern_str, re.IGNORECASE)
            except re.error:
                self._search_pattern = re.compile(re.escape(pattern_str), re.IGNORECASE)
        # Close the search bar after submission
        self._hide_search()

    # ------------------------------------------------------------------
    # Actions (keyboard bindings)
    # ------------------------------------------------------------------

    def action_toggle_panel(self, index_str: str) -> None:
        """Toggle visibility of panel at the given 1-based index."""
        idx = int(index_str) - 1
        if idx < 0 or idx >= len(self._panel_order):
            return
        key = self._panel_order[idx]
        panel = self._panels[key]
        panel.toggle_class("user-hidden")
        self._reflow_panels()

    def action_equalize(self) -> None:
        """Set all visible panels to equal width."""
        for key in self._panel_order:
            self._panel_sizes[key] = 1
        self._reflow_panels()

    def _focused_panel_key(self) -> str | None:
        """Return the key of the currently focused panel, if any."""
        focused = self.focused
        if focused is None:
            return None
        # Walk up to find the LogPanel ancestor
        node = focused
        while node is not None:
            if isinstance(node, LogPanel):
                return node.panel_key
            node = node.parent  # type: ignore[assignment]
        return None

    def action_grow_panel(self) -> None:
        """Increase the focused panel's width weight."""
        key = self._focused_panel_key()
        if key and key in self._panel_sizes:
            self._panel_sizes[key] = min(self._panel_sizes[key] + 1, 10)
            self._reflow_panels()

    def action_shrink_panel(self) -> None:
        """Decrease the focused panel's width weight."""
        key = self._focused_panel_key()
        if key and key in self._panel_sizes:
            self._panel_sizes[key] = max(self._panel_sizes[key] - 1, 1)
            self._reflow_panels()

    def action_focus_next_panel(self) -> None:
        """Move focus to the next visible panel's RichLog."""
        visible = [k for k in self._panel_order if self._panels[k].display]
        if not visible:
            return
        current = self._focused_panel_key()
        idx = (visible.index(current) + 1) % len(visible) if current in visible else 0
        self._panels[visible[idx]].rich_log.focus()

    def action_focus_prev_panel(self) -> None:
        """Move focus to the previous visible panel's RichLog."""
        visible = [k for k in self._panel_order if self._panels[k].display]
        if not visible:
            return
        current = self._focused_panel_key()
        if current in visible:
            idx = (visible.index(current) - 1) % len(visible)
        else:
            idx = len(visible) - 1
        self._panels[visible[idx]].rich_log.focus()

    def action_toggle_auto_scroll(self) -> None:
        """Toggle auto-scroll on all panels."""
        self._auto_scroll = not self._auto_scroll
        for panel in self._panels.values():
            panel.rich_log.auto_scroll = self._auto_scroll

    def action_toggle_sidebar(self) -> None:
        """Toggle the sidebar visibility."""
        sidebar = self.query_one("#log-sidebar", LogSidebar)
        sidebar.display = not sidebar.display

    def action_minimize_panel(self) -> None:
        """Minimize or restore the focused panel."""
        key = self._focused_panel_key()
        if key and key in self._panels:
            panel = self._panels[key]
            panel.is_minimized = not panel.is_minimized

    def action_open_search(self) -> None:
        """Show the search bar and focus the input."""
        search_bar = self.query_one("#search-bar", SearchBar)
        search_bar.add_class("visible")
        self._search_visible = True
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def _hide_search(self) -> None:
        """Hide the search bar."""
        search_bar = self.query_one("#search-bar", SearchBar)
        search_bar.remove_class("visible")
        self._search_visible = False

    def action_show_help(self) -> None:
        """Show the help overlay."""
        self.push_screen(HelpScreen())

    def action_dismiss_overlays(self) -> None:
        """Dismiss search bar or sidebar selection."""
        if self._search_visible:
            self._hide_search()
            return
        if self._selected_log is not None:
            self._selected_log = None
            self._reflow_panels()
            return

    # ------------------------------------------------------------------
    # Filtering helper
    # ------------------------------------------------------------------

    def _filter_logs(self, logs: list[BuildLog]) -> list[BuildLog]:
        return filter_logs(
            logs,
            show_import=self._show_import,
            show_srpm=self._show_srpm,
            show_rpm=self._show_rpm,
            log_types=self._log_types,
            chroots=self._chroots,
        )

    # Log-level color rules: each entry is (compiled pattern, Rich style).
    # Checked top-to-bottom; first match wins.
    _LOG_COLOR_RULES: list[tuple[re.Pattern[str], str]] = [
        # Errors / failures — bold red
        (
            re.compile(
                r"(?i)\berror[\s:\[]|^error\b|FAILED|"
                r"\bfatal\b|\btraceback\b|"
                r"^make\[\d+\]: \*\*\*"
            ),
            "bold red",
        ),
        # Warnings / deprecations — yellow
        (
            re.compile(r"(?i)\bwarning[\s:\[]|^warning\b|\bdeprecated\b"),
            "yellow",
        ),
        # Shell trace lines (+ cmd / ++ cmd) — cyan
        (re.compile(r"^\+{1,3} "), "cyan"),
        # RPM build phases — bold magenta
        (re.compile(r"^Executing\(%\w+\)"), "bold magenta"),
        # Section separators — bold blue
        (re.compile(r"^={3,}|^-{3,}"), "bold blue"),
        # Debug — dim
        (re.compile(r"(?i)^debug\b"), "dim"),
        # Installed / passed / success — green
        (
            re.compile(
                r"(?i)^Installed:|^Complete!|"
                r"\bPASSED\b|\bSUCCESS\b|"
                r"\bok\b.*$"
            ),
            "green",
        ),
        # Timestamps / process headers — dim italic
        (re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}"), "dim italic"),
    ]

    @staticmethod
    def _colorize_plain_line(text: Text) -> None:
        """Apply log-level coloring to a plain-text line (no ANSI)."""
        plain = text.plain
        for pattern, style in BuildTUI._LOG_COLOR_RULES:
            if pattern.search(plain):
                text.stylize(style)
                return

    def _parse_lines(self, content: str) -> list[Text]:
        """Parse raw log content into Rich Text lines, preserving ANSI colors.

        Lines that already contain ANSI escape sequences keep their
        original styling.  Plain-text lines are colorized by log-level
        patterns (errors → red, warnings → yellow, shell traces → cyan,
        etc.) so the output is never all-white.
        """
        result: list[Text] = []
        for line in content.rstrip().split("\n"):
            if self._grep and not self._grep.search(line):
                continue

            text = Text.from_ansi(line)

            # If Text.from_ansi found no ANSI codes the line has no
            # style spans → apply our own log-level coloring.
            if not text._spans:
                self._colorize_plain_line(text)

            # Apply runtime search highlight (from '/' search)
            if self._search_pattern and self._search_pattern.search(line):
                plain = text.plain
                for match in self._search_pattern.finditer(plain):
                    text.stylize(
                        "bold reverse yellow",
                        match.start(),
                        match.end(),
                    )
            result.append(text)
        return result

    # ------------------------------------------------------------------
    # Workers (run in background threads)
    # ------------------------------------------------------------------

    def _stream_build_worker(self) -> None:
        """Background worker: stream logs for a single build."""
        assert self._build is not None
        build = self._build
        start_time = time.monotonic()
        seen_log_urls: set[str] = set()
        active_logs: list[BuildLog] = []
        completed_logs: set[str] = set()

        cache = LogCache()
        cache.prune()

        with (
            LogStreamer(poll_interval=self._poll_interval, cache=cache) as streamer,
            CoprService() as copr,
        ):
            current_build = build

            while True:
                # Refresh build state
                with contextlib.suppress(Exception):
                    current_build = copr.get_build(build.id)

                # Elapsed time
                elapsed = format_elapsed(time.monotonic() - start_time)
                pkg = current_build.package_name or "unknown"
                info = (
                    f"Build #{current_build.id} — "
                    f"{current_build.owner}/{current_build.project} — "
                    f"{pkg} — ⏱ {elapsed} — "
                    f"{current_build.state.value}"
                )
                self.post_message(BuildInfoUpdated(info))

                # Discover logs
                chroot_filter = (
                    self._chroots[0]
                    if self._chroots and len(self._chroots) == 1
                    else None
                )
                all_logs = current_build.get_all_log_urls(chroot=chroot_filter)
                filtered_logs = self._filter_logs(all_logs)

                for log in filtered_logs:
                    if log.url not in seen_log_urls:
                        seen_log_urls.add(log.url)
                        active_logs.append(log)

                # Fetch content concurrently and coalesce by panel key
                pending = [log for log in active_logs if log.url not in completed_logs]
                chunks = streamer.get_new_content_batch(pending)
                self._post_coalesced_chunks(chunks)

                # Check completions
                logs_to_remove: list[BuildLog] = []
                for log in pending:
                    if streamer.is_log_complete(log):
                        final_chunk = streamer.get_new_content(log)
                        if final_chunk:
                            self._post_chunk(final_chunk)
                        completed_logs.add(log.url)
                        logs_to_remove.append(log)

                for log in logs_to_remove:
                    active_logs.remove(log)

                # Check if done
                if (
                    current_build.state.is_finished
                    and not active_logs
                    and len(completed_logs) == len(filtered_logs)
                ):
                    break

                interruptible_sleep(self._poll_interval)

        self.post_message(StreamingComplete())

    def _watch_project_worker(self) -> None:
        """Background worker: watch a project for new builds."""
        assert self._owner is not None and self._project is not None
        seen_builds: set[int] = set()

        with CoprService() as copr:
            while True:
                try:
                    running = copr.get_running_builds(self._owner, self._project)
                    pending = copr.get_pending_builds(self._owner, self._project)
                    active_builds = running + pending

                    if self._package:
                        active_builds = [
                            b for b in active_builds if b.package_name == self._package
                        ]

                    for build in active_builds:
                        if build.id not in seen_builds:
                            seen_builds.add(build.id)
                            info = (
                                f"Watching {self._owner}/{self._project}"
                                + (
                                    f" (package: {self._package})"
                                    if self._package
                                    else ""
                                )
                                + f" — New build #{build.id}"
                            )
                            self.post_message(BuildInfoUpdated(info))
                            # Stream this build inline
                            self._build = build
                            self._stream_build_worker()

                except KeyboardInterrupt:
                    raise
                except Exception:
                    pass

                interruptible_sleep(self._poll_interval)

    def _post_chunk(self, chunk: LogChunk) -> None:
        """Parse a chunk and post it as a message."""
        key = self._chroot_key(chunk.log)
        title = self._chroot_title(key)
        lines = self._parse_lines(chunk.content)
        if lines:
            self.post_message(ChunkReceived(key=key, title=title, lines=lines))

    def _post_coalesced_chunks(self, chunks: list[LogChunk]) -> None:
        """Coalesce chunks by panel key and post one message per panel.

        This reduces the number of UI message handler invocations from
        N (one per chunk) to at most P (one per panel), which means
        fewer layout reflows per poll cycle.
        """
        coalesced: dict[str, list[Text]] = {}
        titles: dict[str, str] = {}

        for chunk in chunks:
            key = self._chroot_key(chunk.log)
            if key not in titles:
                titles[key] = self._chroot_title(key)
            lines = self._parse_lines(chunk.content)
            if lines:
                coalesced.setdefault(key, []).extend(lines)

        for key, lines in coalesced.items():
            self.post_message(ChunkReceived(key=key, title=titles[key], lines=lines))
