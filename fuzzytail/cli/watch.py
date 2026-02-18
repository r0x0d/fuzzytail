"""Watch command for monitoring COPR builds."""

from typing import Annotated

import cyclopts
from rich.console import Console

from fuzzytail.models import BuildLogType
from fuzzytail.services.copr import CoprError

console = Console()


def watch_cmd(
    project: Annotated[
        str,
        cyclopts.Parameter(help="COPR project in 'owner/project' format"),
    ],
    *,
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
    srpm: Annotated[
        bool,
        cyclopts.Parameter(
            ["--srpm"],
            help="Include SRPM build logs",
        ),
    ] = True,
    rpm: Annotated[
        bool,
        cyclopts.Parameter(
            ["--rpm"],
            help="Include RPM build logs",
        ),
    ] = True,
    builder_live: Annotated[
        bool,
        cyclopts.Parameter(
            ["--builder-live", "-l"],
            help="Include builder-live logs",
        ),
    ] = True,
    backend: Annotated[
        bool,
        cyclopts.Parameter(
            ["--backend", "-B"],
            help="Include backend logs",
        ),
    ] = True,
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
    poll_interval: Annotated[
        float,
        cyclopts.Parameter(
            ["--interval", "-i"],
            help="Poll interval in seconds for checking new builds",
        ),
    ] = 5.0,
    grep: Annotated[
        str | None,
        cyclopts.Parameter(
            ["--grep", "-g"],
            help="Filter log lines by regex pattern (like grep)",
        ),
    ] = None,
) -> None:
    """Watch a project for new builds and stream their logs.

    This command continuously monitors the specified COPR project for new builds
    and streams their logs in real-time as they become available.

    Examples:
        fuzzytail watch owner/project
        fuzzytail watch owner/project --package broot --chroot fedora-43-x86_64
        fuzzytail watch owner/project --grep "error|warning"
    """
    from fuzzytail.ui.tui import BuildTUI

    if "/" not in project:
        console.print("[red]Error: Project must be in 'owner/project' format[/red]")
        raise SystemExit(1)

    owner, project_name = project.split("/", 1)

    # Determine log type filters
    log_types = []
    if backend and not skip_backend:
        log_types.append(BuildLogType.BACKEND)
    if builder_live:
        log_types.append(BuildLogType.BUILDER_LIVE)

    if not log_types:
        log_types = None  # Show all if nothing selected

    chroots = [chroot] if chroot else None

    try:
        tui = BuildTUI(
            owner=owner,
            project=project_name,
            package=package,
            show_import=not skip_import,
            show_srpm=srpm,
            show_rpm=rpm,
            log_types=log_types,
            chroots=chroots,
            grep_pattern=grep,
            poll_interval=poll_interval,
        )
        tui.run()
    except CoprError as e:
        console.print(f"[red]COPR Error: {e}[/red]")
        raise SystemExit(1) from e
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
