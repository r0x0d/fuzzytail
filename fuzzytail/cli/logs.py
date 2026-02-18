"""Logs command for fetching specific build logs."""

import re
from typing import TYPE_CHECKING, Annotated

import cyclopts
from rich.console import Console
from rich.prompt import IntPrompt
from rich.table import Table
from rich.text import Text

from fuzzytail.models import Build, BuildLogType

if TYPE_CHECKING:
    from fuzzytail.services.copr import CoprService

console = Console()


def logs_cmd(
    project: Annotated[
        str,
        cyclopts.Parameter(help="COPR project in 'owner/project' format"),
    ],
    *,
    build_id: Annotated[
        int | None,
        cyclopts.Parameter(
            ["--build", "-b"],
            help="Specific build ID to fetch logs for",
        ),
    ] = None,
    package: Annotated[
        str | None,
        cyclopts.Parameter(
            ["--package", "-p"],
            help="Filter by package name",
        ),
    ] = None,
    chroot: Annotated[
        str | None,
        cyclopts.Parameter(
            ["--chroot", "-c"],
            help="Filter by chroot",
        ),
    ] = None,
    log_type: Annotated[
        str | None,
        cyclopts.Parameter(
            ["--type", "-t"],
            help="Log type: 'import', 'builder-live', or 'backend'",
        ),
    ] = None,
    srpm_only: Annotated[
        bool,
        cyclopts.Parameter(
            ["--srpm-only"],
            help="Only show SRPM logs",
        ),
    ] = False,
    rpm_only: Annotated[
        bool,
        cyclopts.Parameter(
            ["--rpm-only"],
            help="Only show RPM logs",
        ),
    ] = False,
    skip_backend: Annotated[
        bool,
        cyclopts.Parameter(
            ["--skip-backend"],
            help="Skip backend logs (show only builder-live)",
        ),
    ] = False,
    skip_import: Annotated[
        bool,
        cyclopts.Parameter(
            ["--skip-import"],
            help="Skip import (dist-git) logs",
        ),
    ] = False,
    follow: Annotated[
        bool,
        cyclopts.Parameter(
            ["--follow", "-f"],
            help="Follow logs in real-time (like tail -f)",
        ),
    ] = False,
    poll_interval: Annotated[
        float,
        cyclopts.Parameter(
            ["--interval", "-i"],
            help="Poll interval in seconds when following",
        ),
    ] = 2.0,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            ["--limit", "-n"],
            help="Number of builds to show when selecting",
        ),
    ] = 10,
    grep: Annotated[
        str | None,
        cyclopts.Parameter(
            ["--grep", "-g"],
            help="Filter log lines by regex pattern (like grep)",
        ),
    ] = None,
) -> None:
    """Fetch and display logs for a build.

    If no build ID is specified, shows recent builds and prompts for selection.

    Examples:
        fuzzytail logs owner/project
        fuzzytail logs owner/project --build 12345678
        fuzzytail logs owner/project --package broot
        fuzzytail logs owner/project --type builder-live --follow
        fuzzytail logs owner/project --build 12345678 --grep "error|warning"
    """
    from fuzzytail.services.copr import CoprError, CoprService

    # Validate project format
    if "/" not in project:
        console.print("[red]Error: Project must be in 'owner/project' format[/red]")
        raise SystemExit(1)

    owner, project_name = project.split("/", 1)

    # Parse log type
    log_types = None
    if skip_backend:
        log_types = [BuildLogType.BUILDER_LIVE]
    elif log_type:
        try:
            log_types = [BuildLogType(log_type)]
        except ValueError:
            console.print(
                f"[red]Invalid log type: {log_type}. "
                f"Use 'import', 'builder-live', or 'backend'.[/red]"
            )
            raise SystemExit(1) from None

    show_srpm = not rpm_only
    show_rpm = not srpm_only
    chroots = [chroot] if chroot else None

    try:
        with CoprService() as copr:
            # If build_id provided, use it directly
            if build_id:
                build = copr.get_build(build_id)
            else:
                # Fetch recent builds and let user choose
                builds = copr.get_project_builds(
                    owner,
                    project_name,
                    package=package,
                    limit=limit,
                )

                if not builds:
                    console.print("[yellow]No builds found.[/yellow]")
                    return

                if len(builds) == 1:
                    # Only one build, use it directly
                    build = copr.get_build(builds[0].id)
                    console.print(
                        f"[dim]Using build #{build.id} "
                        f"({build.package_name or 'unknown'})[/dim]\n"
                    )
                else:
                    # Multiple builds, show selection
                    build = _select_build(builds, copr)
                    if build is None:
                        return

            if follow:
                # Launch the TUI for live streaming
                from fuzzytail.ui.tui import BuildTUI

                tui = BuildTUI(
                    build=build,
                    show_import=not skip_import,
                    show_srpm=show_srpm,
                    show_rpm=show_rpm,
                    log_types=log_types,
                    chroots=chroots,
                    grep_pattern=grep,
                    poll_interval=poll_interval,
                )
                tui.run()
            else:
                # Fetch and display complete logs (one-shot, non-interactive)
                grep_re: re.Pattern[str] | None = None
                if grep:
                    try:
                        grep_re = re.compile(grep, re.IGNORECASE)
                    except re.error:
                        grep_re = re.compile(re.escape(grep), re.IGNORECASE)

                _display_complete_logs(
                    build,
                    chroot=chroot,
                    show_import=not skip_import,
                    show_srpm=show_srpm,
                    show_rpm=show_rpm,
                    log_types=log_types,
                    chroots_filter=chroots,
                    grep_re=grep_re,
                )

    except CoprError as e:
        console.print(f"[red]COPR Error: {e}[/red]")
        raise SystemExit(1) from e
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")


def _select_build(builds: list[Build], copr: "CoprService") -> Build | None:
    """Display builds and prompt user to select one.

    Args:
        builds: List of builds to choose from.
        copr: CoprService instance for fetching full build details.

    Returns:
        Selected Build object, or None if cancelled.
    """
    from fuzzytail.ui.panels import get_state_icon, get_state_style

    console.print("[bold]Select a build:[/bold]\n")

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("#", style="dim", width=4)
    table.add_column("Build ID", style="cyan")
    table.add_column("Package", style="green")
    table.add_column("State")
    table.add_column("Chroots", style="dim")

    build_map: dict[int, Build] = {}

    for idx, build in enumerate(builds, 1):
        build_map[idx] = build

        state_text = Text()
        icon = get_state_icon(build.state)
        state_text.append(
            f"{icon} {build.state.value}", style=get_state_style(build.state)
        )

        chroot_names = ", ".join(c.name for c in build.chroots[:2])
        if len(build.chroots) > 2:
            chroot_names += f" (+{len(build.chroots) - 2})"

        table.add_row(
            str(idx),
            str(build.id),
            build.package_name or "-",
            state_text,
            chroot_names or "-",
        )

    console.print(table)
    console.print()

    try:
        choice = IntPrompt.ask(
            "Enter build number",
            choices=[str(i) for i in range(1, len(builds) + 1)],
            show_choices=False,
        )
        selected = build_map[choice]
        console.print()

        # Fetch full build details
        return copr.get_build(selected.id)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        return None


def _display_complete_logs(
    build: Build,
    *,
    chroot: str | None,
    show_import: bool,
    show_srpm: bool,
    show_rpm: bool,
    log_types: list[BuildLogType] | None,
    chroots_filter: list[str] | None,
    grep_re: re.Pattern[str] | None,
) -> None:
    """Display complete (non-streaming) logs for a build.

    Args:
        build: The Build object.
        chroot: Optional chroot filter for log URLs.
        show_import: Whether to include import logs.
        show_srpm: Whether to include SRPM logs.
        show_rpm: Whether to include RPM logs.
        log_types: Specific log types to show.
        chroots_filter: Specific chroots to filter.
        grep_re: Compiled regex for filtering lines.
    """
    from fuzzytail.services.logs import LogStreamer
    from fuzzytail.ui.panels import BuildPanel
    from fuzzytail.utils import filter_logs

    # Show build info
    build_panel = BuildPanel(build)
    console.print(build_panel.render())
    console.print()

    # Get logs
    all_logs = build.get_all_log_urls(chroot=chroot)
    logs = filter_logs(
        all_logs,
        show_import=show_import,
        show_srpm=show_srpm,
        show_rpm=show_rpm,
        log_types=log_types,
        chroots=chroots_filter,
    )

    if not logs:
        console.print("[yellow]No logs match the specified filters.[/yellow]")
        return

    with LogStreamer() as streamer:
        for log in logs:
            content = streamer.fetch_log(log)
            if content:
                # Print log header
                console.print(f"\n[bold cyan]── {log.display_name} ──[/bold cyan]\n")
                if grep_re:
                    for line in content.split("\n"):
                        if grep_re.search(line):
                            console.print(Text.from_ansi(line))
                else:
                    # Preserve ANSI colors from COPR logs
                    for line in content.split("\n"):
                        console.print(Text.from_ansi(line))
                console.print()
            else:
                console.print(
                    f"[dim]No content available for {log.display_name}[/dim]\n"
                )
