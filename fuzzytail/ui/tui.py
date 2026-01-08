"""Textual TUI application for interactive log streaming with search."""

import re
from typing import Optional

from rich.highlighter import ReprHighlighter
from rich.style import Style
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, RichLog, Static

from fuzzytail.models import Build, BuildLog, BuildLogType, LogSource
from fuzzytail.services.copr import CoprService
from fuzzytail.services.logs import LogChunk, LogStreamer, categorize_logs

# Rich's default highlighter for syntax coloring
_highlighter = ReprHighlighter()

# Try to import pyperclip for clipboard support
try:
    import pyperclip

    HAS_PYPERCLIP = True
except ImportError:
    pyperclip = None  # type: ignore[assignment]
    HAS_PYPERCLIP = False


class SearchBar(Static):
    """Search input bar that appears at the bottom of the screen."""

    DEFAULT_CSS = """
    SearchBar {
        dock: bottom;
        height: auto;
        display: none;
        background: transparent;
        padding: 0 1;
    }

    SearchBar.visible {
        display: block;
    }

    SearchBar Input {
        width: 100%;
        border: none;
        background: transparent;
        padding: 0;
    }

    SearchBar Input:focus {
        border: none;
    }

    SearchBar .search-label {
        text-style: bold;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("/", classes="search-label")
        yield Input(
            placeholder="Search pattern (regex supported)...", id="search-input"
        )

    def show(self) -> None:
        """Show the search bar and focus the input."""
        self.add_class("visible")
        self.query_one("#search-input", Input).focus()

    def hide(self) -> None:
        """Hide the search bar."""
        self.remove_class("visible")
        self.query_one("#search-input", Input).value = ""

    @property
    def is_visible(self) -> bool:
        """Check if search bar is visible."""
        return self.has_class("visible")

    @property
    def value(self) -> str:
        """Get the current search value."""
        return self.query_one("#search-input", Input).value


class HelpBar(Static):
    """Help bar showing available keybindings."""

    DEFAULT_CSS = """
    HelpBar {
        dock: bottom;
        height: 1;
        background: transparent;
        padding: 0 1;
        text-style: dim;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold]/[/bold] Search  [bold]n[/bold]/[bold]N[/bold] Next/Prev  "
            "[bold]y[/bold] Copy  [bold]q[/bold] Quit  "
            "[dim]Shift+Mouse to select text[/dim]",
            id="help-text",
        )


class StatusBar(Static):
    """Status bar showing build info and search status."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: transparent;
        padding: 0 1;
    }

    StatusBar .status-left {
        width: 1fr;
        text-style: bold;
    }

    StatusBar .status-right {
        width: auto;
        text-align: right;
        text-style: dim italic;
    }
    """

    build_info: reactive[str] = reactive("")
    search_info: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Static(self.build_info, classes="status-left", id="status-left")
        yield Static(self.search_info, classes="status-right", id="status-right")

    def watch_build_info(self, value: str) -> None:
        """Update build info display."""
        try:
            self.query_one("#status-left", Static).update(value)
        except Exception:
            pass

    def watch_search_info(self, value: str) -> None:
        """Update search info display."""
        try:
            self.query_one("#status-right", Static).update(value)
        except Exception:
            pass


class LogView(RichLog):
    """Scrollable log view with search highlighting."""

    DEFAULT_CSS = """
    LogView {
        height: 1fr;
        border: none;
        scrollbar-gutter: stable;
        background: transparent;
        scrollbar-background: transparent;
        scrollbar-color: ansi_bright_black;
        scrollbar-color-hover: ansi_white;
        scrollbar-color-active: ansi_white;
    }
    """

    # Track selected text for copy functionality
    _selected_lines: list[int] = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, highlight=True, markup=True, wrap=True, **kwargs)
        self._lines: list[str] = []
        self._raw_lines: list[str] = []  # Store raw lines without markup for search
        self._search_pattern: Optional[re.Pattern] = None
        self._match_positions: list[tuple[int, int, int]] = []  # (line_idx, start, end)
        self._current_match_idx: int = -1
        self._search_active: bool = (
            False  # Track if search is active to disable auto-scroll
        )

    @property
    def match_count(self) -> int:
        """Get the number of search matches."""
        return len(self._match_positions)

    @property
    def current_match(self) -> int:
        """Get the current match index (1-based for display)."""
        return self._current_match_idx + 1 if self._current_match_idx >= 0 else 0

    def add_line(self, line: str, auto_scroll: bool = True) -> None:
        """Add a line to the log and check for matches."""
        line_idx = len(self._lines)
        self._lines.append(line)

        # Store raw text (without markup) for searching - do this lazily only if needed
        if self._search_pattern:
            try:
                raw_text = Text.from_markup(line).plain
            except Exception:
                raw_text = line
            self._raw_lines.append(raw_text)

            # Check for matches in the raw text
            for match in self._search_pattern.finditer(raw_text):
                self._match_positions.append((line_idx, match.start(), match.end()))

            # Use Text object with search highlighting
            self.write(self._highlight_line(line), scroll_end=False)
        else:
            # Store raw text for potential future searches
            try:
                raw_text = Text.from_markup(line).plain
            except Exception:
                raw_text = line
            self._raw_lines.append(raw_text)

            # Pass raw string to enable Rich's syntax highlighting
            # Disable scroll_end here - caller handles scrolling
            self.write(line, scroll_end=False)

        # Only scroll if requested (caller batches this)
        if auto_scroll and not self._search_active:
            self.scroll_end(animate=False)

    def _highlight_line(self, line: str) -> Text:
        """Highlight search matches in a line, preserving Rich markup and syntax colors."""
        # Parse Rich markup first
        try:
            text = Text.from_markup(line)
        except Exception:
            text = Text(line)

        # Apply Rich's syntax highlighting (numbers, strings, URLs, etc.)
        text = _highlighter(text)

        # Apply search highlighting on top
        if self._search_pattern:
            plain = text.plain
            for match in self._search_pattern.finditer(plain):
                text.stylize(
                    Style(bgcolor="yellow", color="black", bold=True),
                    match.start(),
                    match.end(),
                )
        return text

    def set_search_pattern(self, pattern: str) -> None:
        """Set the search pattern and reindex matches."""
        self._match_positions = []
        self._current_match_idx = -1

        if not pattern:
            self._search_pattern = None
            self._search_active = False
            self._refresh_display()
            return

        try:
            self._search_pattern = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Fall back to literal search if regex is invalid
            self._search_pattern = re.compile(re.escape(pattern), re.IGNORECASE)

        # Mark search as active to disable auto-scroll
        self._search_active = True

        # Reindex all existing lines using raw text
        for line_idx, raw_line in enumerate(self._raw_lines):
            for match in self._search_pattern.finditer(raw_line):
                self._match_positions.append((line_idx, match.start(), match.end()))

        self._refresh_display()

        # Go to first match if any
        if self._match_positions:
            self._current_match_idx = 0
            self._scroll_to_match(0)

    def get_all_text(self) -> str:
        """Get all log text as plain string for copying."""
        return "\n".join(self._raw_lines)

    def get_matching_lines(self) -> list[str]:
        """Get all lines that contain search matches."""
        if not self._search_pattern or not self._match_positions:
            return []

        # Get unique line indices that have matches
        matching_line_indices = sorted(set(pos[0] for pos in self._match_positions))
        return [self._raw_lines[idx] for idx in matching_line_indices]

    def get_matching_text(self) -> str:
        """Get matching lines as a single string for copying."""
        return "\n".join(self.get_matching_lines())

    def _refresh_display(self) -> None:
        """Refresh the entire display with current highlighting."""
        self.clear()
        # Batch all writes without scrolling, then scroll once at end
        for line in self._lines:
            if self._search_pattern:
                self.write(self._highlight_line(line), scroll_end=False)
            else:
                self.write(line, scroll_end=False)

    def next_match(self) -> None:
        """Go to the next search match."""
        if not self._match_positions:
            return
        self._current_match_idx = (self._current_match_idx + 1) % len(
            self._match_positions
        )
        self._scroll_to_match(self._current_match_idx)

    def prev_match(self) -> None:
        """Go to the previous search match."""
        if not self._match_positions:
            return
        self._current_match_idx = (self._current_match_idx - 1) % len(
            self._match_positions
        )
        self._scroll_to_match(self._current_match_idx)

    def _scroll_to_match(self, match_idx: int) -> None:
        """Scroll to show a specific match."""
        if 0 <= match_idx < len(self._match_positions):
            line_idx, _, _ = self._match_positions[match_idx]
            # Scroll to the line containing the match
            self.scroll_to(y=line_idx, animate=False)

    def clear_search(self) -> None:
        """Clear the search pattern and re-enable auto-scroll."""
        self._search_active = False
        self.set_search_pattern("")


class FuzzytailApp(App):
    """Main Textual application for fuzzytail."""

    TITLE = "fuzzytail"
    SUB_TITLE = "COPR Build Log Viewer"

    # Use ANSI colors from terminal theme
    ENABLE_COMMAND_PALETTE = False

    # Enable mouse support for scrolling and interaction
    MOUSE_SUPPORT = True

    CSS = """
    Screen {
        background: transparent;
    }

    #main-container {
        height: 100%;
        background: transparent;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("slash", "open_search", "Search", show=True, key_display="/"),
        Binding("n", "next_match", "Next", show=True),
        Binding("N", "prev_match", "Previous", show=True, key_display="N"),
        Binding("escape", "close_search", "Close Search", show=False),
        Binding("y", "copy_all", "Copy All", show=True),
        Binding("ctrl+c", "copy_or_quit", "Copy/Quit", show=False),
    ]

    class LogUpdated(Message):
        """Message sent when log content is updated."""

        pass

    def __init__(
        self,
        owner: str,
        project: str,
        package: Optional[str] = None,
        chroot: Optional[str] = None,
        build_id: Optional[int] = None,
        show_import: bool = True,
        show_srpm: bool = True,
        show_rpm: bool = True,
        log_types: Optional[list[BuildLogType]] = None,
        poll_interval: float = 2.0,
    ) -> None:
        # Use ANSI colors from terminal to inherit theme
        super().__init__(ansi_color=True)
        self.owner = owner
        self.project_name = project
        self.package = package
        self.chroot = chroot
        self.build_id = build_id
        self.show_import = show_import
        self.show_srpm = show_srpm
        self.show_rpm = show_rpm
        self.log_types = log_types
        self.chroots = [chroot] if chroot else None
        self.poll_interval = poll_interval
        self._stop = False
        self._seen_log_urls: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Container(
            LogView(id="log-view"),
            id="main-container",
        )
        yield StatusBar(id="status-bar")
        yield HelpBar(id="help-bar")
        yield SearchBar(id="search-bar")

    def on_mount(self) -> None:
        """Start streaming when the app is mounted."""
        # Show header info in the log view
        header = f"[bold]Watching {self.owner}/{self.project_name}[/bold]"
        if self.package:
            header += f" [dim](package: {self.package})[/dim]"
        self._add_log_lines_sync([header, ""])

        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.build_info = f"Watching {self.owner}/{self.project_name}"
        self.start_streaming()

    @work(thread=True)
    def start_streaming(self) -> None:
        """Start streaming logs in a background thread."""
        if self.build_id:
            self._stream_single_build()
        else:
            self._watch_project()

    def _stream_single_build(self) -> None:
        """Stream logs for a specific build."""
        assert self.build_id is not None
        with CoprService() as copr:
            build = copr.get_build(self.build_id)
            self._update_status(f"Build #{build.id} - {build.package_name}")
            self._add_log_line(f"Streaming logs for build #{build.id}...")
            self._add_log_line("")
            self._stream_build_logs(build, copr)

    def _watch_project(self) -> None:
        """Watch project for new builds."""
        seen_builds: set[int] = set()

        with CoprService() as copr:
            while not self._stop:
                try:
                    running = copr.get_running_builds(self.owner, self.project_name)
                    pending = copr.get_pending_builds(self.owner, self.project_name)

                    active_builds = running + pending

                    if self.package:
                        active_builds = [
                            b for b in active_builds if b.package_name == self.package
                        ]

                    for build in active_builds:
                        if build.id not in seen_builds:
                            seen_builds.add(build.id)
                            self._add_log_line(
                                f"\n[cyan]New build detected: "
                                f"#{build.id} ({build.package_name})[/cyan]"
                            )
                            self._update_status(
                                f"Build #{build.id} - {build.package_name}"
                            )
                            self._stream_build_logs(build, copr)

                    if not active_builds:
                        self._update_status(
                            f"Watching {self.owner}/{self.project_name} - No active builds"
                        )

                except Exception as e:
                    self._add_log_line(f"[red]Error: {e}[/red]")

                self._interruptible_sleep(self.poll_interval)

    def _stream_build_logs(self, build: Build, copr: CoprService) -> None:
        """Stream logs for a build."""
        self._seen_log_urls = set()

        with LogStreamer(poll_interval=self.poll_interval) as streamer:
            current_build = build
            active_logs: list[BuildLog] = []
            completed_logs: set[str] = set()

            while not self._stop:
                # Refresh build state
                try:
                    current_build = copr.get_build(build.id)
                except Exception:
                    pass

                # Get all available logs
                chroot_filter = (
                    self.chroots[0] if self.chroots and len(self.chroots) == 1 else None
                )
                all_logs = current_build.get_all_log_urls(chroot=chroot_filter)
                filtered_logs = self._filter_logs(all_logs)

                # Find new logs
                for log in filtered_logs:
                    if log.url not in self._seen_log_urls:
                        self._seen_log_urls.add(log.url)
                        active_logs.append(log)
                        self._add_log_line(
                            f"\n[cyan]Discovered log: {log.display_name}[/cyan]"
                        )
                        self._add_log_header(log)

                # Stream active logs
                logs_to_remove = []
                for log in active_logs:
                    if log.url in completed_logs:
                        continue

                    chunk = streamer.get_new_content(log)
                    if chunk:
                        self._on_chunk(chunk)

                    if streamer.is_log_complete(log):
                        final_chunk = streamer.get_new_content(log)
                        if final_chunk:
                            self._on_chunk(final_chunk)
                        completed_logs.add(log.url)
                        logs_to_remove.append(log)

                for log in logs_to_remove:
                    active_logs.remove(log)

                # Check if build is finished
                if current_build.state.is_finished:
                    if not active_logs and len(completed_logs) == len(filtered_logs):
                        self._add_log_line(
                            "\n[bold green]All logs complete![/bold green]"
                        )
                        break

                self._interruptible_sleep(self.poll_interval)

    def _filter_logs(self, logs: list[BuildLog]) -> list[BuildLog]:
        """Filter logs based on display settings."""
        sources = []
        if self.show_import:
            sources.append(LogSource.IMPORT)
        if self.show_srpm:
            sources.append(LogSource.SRPM)
        if self.show_rpm:
            sources.append(LogSource.RPM)

        return categorize_logs(
            logs,
            log_types=self.log_types,
            sources=sources,
            chroots=self.chroots,
        )

    def _add_log_header(self, log: BuildLog) -> None:
        """Add a log header to the display."""
        header_lines = ["━" * 60]

        if log.source == LogSource.IMPORT:
            header_lines.append("[blue bold]📥 Import (dist-git)[/blue bold]")
        elif log.source == LogSource.SRPM:
            header = f"[cyan bold]📦 SRPM Build[/cyan bold] │ [magenta]{log.log_type.value}[/magenta]"
            if log.is_live:
                header += " │ [green bold]● LIVE[/green bold]"
            header_lines.append(header)
        else:
            header = f"[yellow bold]🔧 {log.chroot}[/yellow bold] │ [magenta]{log.log_type.value}[/magenta]"
            if log.is_live:
                header += " │ [green bold]● LIVE[/green bold]"
            header_lines.append(header)

        header_lines.append("━" * 60)
        # Batch all header lines together
        self._add_log_lines(header_lines)

    def _on_chunk(self, chunk: LogChunk) -> None:
        """Handle a new log chunk."""
        lines = chunk.content.rstrip().split("\n")
        # Batch all lines together for efficiency
        self._add_log_lines(lines)

    def _add_log_line(self, line: str) -> None:
        """Add a single line to the log view (thread-safe)."""
        self._add_log_lines([line])

    def _add_log_lines(self, lines: list[str]) -> None:
        """Add multiple lines to the log view (thread-safe, batched)."""
        if lines:
            self.call_from_thread(self._add_log_lines_sync, lines)

    def _add_log_lines_sync(self, lines: list[str]) -> None:
        """Add multiple lines to the log view (must be called from main thread)."""
        log_view = self.query_one("#log-view", LogView)

        # Batch UI updates for performance
        with self.batch_update():
            for line in lines:
                log_view.add_line(line, auto_scroll=False)

        # Only scroll once at the end if not in search mode
        if not log_view._search_active:
            log_view.scroll_end(animate=False)

        # Only update search info once after batch
        self._update_search_info()

    def _update_status(self, info: str) -> None:
        """Update status bar (thread-safe)."""
        self.call_from_thread(self._update_status_sync, info)

    def _update_status_sync(self, info: str) -> None:
        """Update status bar (must be called from main thread)."""
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.build_info = info

    def _update_search_info(self) -> None:
        """Update search match info in status bar."""
        log_view = self.query_one("#log-view", LogView)
        status_bar = self.query_one("#status-bar", StatusBar)

        if log_view._search_pattern:
            if log_view.match_count > 0:
                status_bar.search_info = (
                    f"Match {log_view.current_match}/{log_view.match_count}"
                )
            else:
                status_bar.search_info = "No matches"
        else:
            status_bar.search_info = ""

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep that checks for stop condition."""
        import time

        elapsed = 0.0
        interval = 0.1
        while elapsed < seconds and not self._stop:
            time.sleep(min(interval, seconds - elapsed))
            elapsed += interval

    def action_open_search(self) -> None:
        """Toggle the search bar - open if closed, close and clear if open."""
        search_bar = self.query_one("#search-bar", SearchBar)
        log_view = self.query_one("#log-view", LogView)

        if search_bar.is_visible:
            # If search bar is open, close it and clear search
            search_bar.hide()
            log_view.clear_search()
            self._update_search_info()
        elif log_view._search_active:
            # If search is active but bar is closed, clear the search
            log_view.clear_search()
            self._update_search_info()
        else:
            # Open search bar
            search_bar.show()

    def action_close_search(self) -> None:
        """Close the search bar and optionally clear search."""
        search_bar = self.query_one("#search-bar", SearchBar)
        if search_bar.is_visible:
            search_bar.hide()
        else:
            # If search bar is closed, pressing Escape clears the search
            log_view = self.query_one("#log-view", LogView)
            log_view.clear_search()
            self._update_search_info()

    def action_next_match(self) -> None:
        """Go to next search match."""
        log_view = self.query_one("#log-view", LogView)
        log_view.next_match()
        self._update_search_info()

    def action_prev_match(self) -> None:
        """Go to previous search match."""
        log_view = self.query_one("#log-view", LogView)
        log_view.prev_match()
        self._update_search_info()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission."""
        if event.input.id == "search-input":
            pattern = event.value
            log_view = self.query_one("#log-view", LogView)
            log_view.set_search_pattern(pattern)
            self._update_search_info()

            search_bar = self.query_one("#search-bar", SearchBar)
            search_bar.hide()

    async def action_quit(self) -> None:
        """Quit the application."""
        self._stop = True
        self.exit()

    def action_copy_all(self) -> None:
        """Copy log content to clipboard - matching lines if searching, all otherwise."""
        if not HAS_PYPERCLIP or pyperclip is None:
            self.notify(
                "Clipboard not available (install pyperclip)", severity="warning"
            )
            return

        log_view = self.query_one("#log-view", LogView)

        # If search is active, copy only matching lines
        if log_view._search_active and log_view.match_count > 0:
            matching_lines = log_view.get_matching_lines()
            text = log_view.get_matching_text()
            try:
                pyperclip.copy(text)
                self.notify(f"Copied {len(matching_lines)} matching lines to clipboard")
            except Exception as e:
                self.notify(f"Failed to copy: {e}", severity="error")
        else:
            # Copy all content
            text = log_view.get_all_text()
            if text:
                try:
                    pyperclip.copy(text)
                    self.notify(f"Copied {len(log_view._raw_lines)} lines to clipboard")
                except Exception as e:
                    self.notify(f"Failed to copy: {e}", severity="error")
            else:
                self.notify("No content to copy", severity="warning")

    async def action_copy_or_quit(self) -> None:
        """Handle Ctrl+C - copy if content selected, otherwise quit."""
        # For now, just quit (Textual handles Ctrl+C as interrupt by default)
        # Mouse selection copy is handled by the terminal itself
        await self.action_quit()
