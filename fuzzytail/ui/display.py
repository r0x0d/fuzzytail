"""Main display component for log streaming."""

from typing import Optional

from rich.console import Console
from rich.text import Text

from fuzzytail.models import Build, BuildLog, BuildLogType, LogSource
from fuzzytail.services.copr import CoprService
from fuzzytail.services.logs import LogChunk, LogStreamer, categorize_logs
from fuzzytail.ui.panels import BuildPanel, get_state_icon


class LogDisplay:
    """Main display for streaming build logs."""

    def __init__(
        self,
        console: Optional[Console] = None,
        show_import: bool = True,
        show_srpm: bool = True,
        show_rpm: bool = True,
        log_types: Optional[list[BuildLogType]] = None,
        chroots: Optional[list[str]] = None,
    ):
        """Initialize the log display.

        Args:
            console: Rich Console instance.
            show_import: Whether to show import (dist-git) logs.
            show_srpm: Whether to show SRPM logs.
            show_rpm: Whether to show RPM logs.
            log_types: Specific log types to show (default: all).
            chroots: Specific chroots to filter (default: all).
        """
        self.console = console or Console()
        self.show_import = show_import
        self.show_srpm = show_srpm
        self.show_rpm = show_rpm
        self.log_types = log_types
        self.chroots = chroots
        self._stop = False
        self._log_content: dict[str, list[str]] = {}
        self._current_log: Optional[BuildLog] = None
        self._seen_log_urls: set[str] = set()

    def _filter_logs(self, logs: list[BuildLog]) -> list[BuildLog]:
        """Filter logs based on display settings.

        Args:
            logs: List of all available logs.

        Returns:
            Filtered list of logs.
        """
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

    def _format_log_header(self, log: BuildLog) -> Text:
        """Format a header for a log section.

        Args:
            log: The BuildLog to format header for.

        Returns:
            Rich Text object.
        """
        text = Text()
        text.append("━" * 60, style="dim")
        text.append("\n")

        if log.source == LogSource.IMPORT:
            text.append("📥 Import (dist-git)", style="blue bold")
        elif log.source == LogSource.SRPM:
            text.append("📦 SRPM Build", style="cyan bold")
            text.append(" │ ", style="dim")
            text.append(log.log_type.value, style="magenta")
        else:
            text.append(f"🔧 {log.chroot}", style="yellow bold")
            text.append(" │ ", style="dim")
            text.append(log.log_type.value, style="magenta")

        if log.is_live:
            text.append(" │ ", style="dim")
            text.append("● LIVE", style="green bold")

        text.append("\n")
        text.append("━" * 60, style="dim")

        return text

    def _on_chunk(self, chunk: LogChunk) -> None:
        """Handle a new log chunk.

        Args:
            chunk: The LogChunk received.
        """
        log_key = chunk.log.url

        if log_key not in self._log_content:
            self._log_content[log_key] = []
            # Print header when we first see this log
            self.console.print(self._format_log_header(chunk.log))

        # Print the new content
        lines = chunk.content.rstrip().split("\n")
        for line in lines:
            self._log_content[log_key].append(line)
            self.console.print(line)

    def stream_build(
        self,
        build: Build,
        poll_interval: float = 2.0,
    ) -> None:
        """Stream logs for a build.

        This method handles the full build lifecycle:
        1. First streams SRPM logs
        2. Then discovers and streams RPM logs as they become available
        3. Periodically refreshes build state to find new chroot builds

        Args:
            build: The Build to stream logs for.
            poll_interval: Seconds between poll attempts.
        """
        # Show build info
        build_panel = BuildPanel(build)
        self.console.print(build_panel.render())
        self.console.print()

        # Start streaming
        self.console.print("[bold green]Starting log stream...[/bold green]\n")

        # Reset seen logs for this build
        self._seen_log_urls = set()

        with LogStreamer(poll_interval=poll_interval) as streamer:
            with CoprService() as copr:
                self._stream_build_with_refresh(build, copr, streamer, poll_interval)

        if not self._stop:
            self.console.print("\n[bold green]All logs complete![/bold green]")

    def _stream_build_with_refresh(
        self,
        build: Build,
        copr: CoprService,
        streamer: LogStreamer,
        poll_interval: float,
    ) -> None:
        """Stream build logs with periodic refresh to discover new logs.

        Args:
            build: The Build to stream.
            copr: CoprService instance.
            streamer: LogStreamer instance.
            poll_interval: Poll interval in seconds.
        """
        current_build = build
        active_logs: list[BuildLog] = []
        completed_logs: set[str] = set()

        while True:
            # Refresh build state to get latest chroot information
            try:
                current_build = copr.get_build(build.id)
            except Exception:
                pass  # Use cached build if refresh fails

            # Get all available logs
            chroot_filter = (
                self.chroots[0] if self.chroots and len(self.chroots) == 1 else None
            )
            all_logs = current_build.get_all_log_urls(chroot=chroot_filter)
            filtered_logs = self._filter_logs(all_logs)

            # Find new logs we haven't seen yet
            for log in filtered_logs:
                if log.url not in self._seen_log_urls:
                    self._seen_log_urls.add(log.url)
                    active_logs.append(log)
                    self.console.print(
                        f"\n[cyan]Discovered log: {log.display_name}[/cyan]"
                    )

            # Stream active logs
            logs_to_remove = []
            for log in active_logs:
                if log.url in completed_logs:
                    continue

                chunk = streamer.get_new_content(log)
                if chunk:
                    self._on_chunk(chunk)

                # Check if log is complete
                if streamer.is_log_complete(log):
                    # Fetch any remaining content
                    final_chunk = streamer.get_new_content(log)
                    if final_chunk:
                        self._on_chunk(final_chunk)
                    completed_logs.add(log.url)
                    logs_to_remove.append(log)

            # Remove completed logs from active list
            for log in logs_to_remove:
                active_logs.remove(log)

            # Check if build is completely finished
            if current_build.state.is_finished:
                # Give it one more cycle to catch any remaining logs
                if not active_logs and len(completed_logs) == len(filtered_logs):
                    break

            # Check for stop condition
            if self._stop:
                break

            # Wait before next poll
            _interruptible_sleep(poll_interval)

    def watch_project(
        self,
        owner: str,
        project: str,
        package: Optional[str] = None,
        poll_interval: float = 5.0,
    ) -> None:
        """Watch a project for new builds and stream their logs.

        Args:
            owner: Project owner username.
            project: Project name.
            package: Optional package name filter.
            poll_interval: Seconds between checking for new builds.
        """
        self.console.print(
            f"[bold]Watching {owner}/{project}"
            + (f" (package: {package})" if package else "")
            + "[/bold]\n"
        )
        self.console.print("[dim]Press Ctrl+C to stop watching...[/dim]\n")

        seen_builds: set[int] = set()

        with CoprService() as copr:
            while True:
                try:
                    # Check for running builds
                    running = copr.get_running_builds(owner, project)
                    pending = copr.get_pending_builds(owner, project)

                    active_builds = running + pending

                    if package:
                        active_builds = [
                            b for b in active_builds if b.package_name == package
                        ]

                    for build in active_builds:
                        if build.id not in seen_builds:
                            seen_builds.add(build.id)
                            self.console.print(
                                f"\n[cyan]New build detected: "
                                f"#{build.id} ({build.package_name})[/cyan]"
                            )
                            self.stream_build(build, poll_interval=2.0)

                    if not active_builds:
                        # Show waiting indicator
                        self.console.print(
                            "[dim]No active builds. Waiting...[/dim]",
                            end="\r",
                        )

                except KeyboardInterrupt:
                    # Re-raise to exit immediately
                    raise
                except Exception as e:
                    self.console.print(f"[red]Error: {e}[/red]")

                # Use interruptible sleep
                _interruptible_sleep(poll_interval)


def _interruptible_sleep(seconds: float, interval: float = 0.1) -> None:
    """Sleep that can be interrupted by KeyboardInterrupt.

    Args:
        seconds: Total seconds to sleep.
        interval: Check interval for interrupts.
    """
    import time

    elapsed = 0.0
    while elapsed < seconds:
        time.sleep(min(interval, seconds - elapsed))
        elapsed += interval


def print_build_summary(build: Build, console: Optional[Console] = None) -> None:
    """Print a summary of a build.

    Args:
        build: The Build to summarize.
        console: Rich Console instance.
    """
    console = console or Console()

    text = Text()
    icon = get_state_icon(build.state)
    text.append(f"{icon} Build #{build.id}", style="bold")
    text.append(f" │ {build.owner}/{build.project}", style="dim")
    if build.package_name:
        text.append(f" │ {build.package_name}", style="cyan")
    text.append(f" │ {build.state.value}")

    console.print(text)


def list_builds(
    builds: list[Build],
    console: Optional[Console] = None,
) -> None:
    """List builds in a table format.

    Args:
        builds: List of builds to display.
        console: Rich Console instance.
    """
    from rich.table import Table

    console = console or Console()

    table = Table(title="COPR Builds", show_header=True)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Package", style="green")
    table.add_column("State", style="yellow")
    table.add_column("Chroots", style="dim")

    for build in builds:
        state_text = Text()
        icon = get_state_icon(build.state)
        state_text.append(f"{icon} {build.state.value}")

        chroots = ", ".join(c.name for c in build.chroots[:3])
        if len(build.chroots) > 3:
            chroots += f" (+{len(build.chroots) - 3})"

        table.add_row(
            str(build.id),
            build.package_name or "-",
            state_text,
            chroots,
        )

    console.print(table)
