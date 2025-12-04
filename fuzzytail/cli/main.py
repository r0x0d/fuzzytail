"""Main CLI application for fuzzytail."""

from typing import Annotated, Optional

import cyclopts
from rich.console import Console

from fuzzytail.cli.builds import builds_cmd
from fuzzytail.cli.logs import logs_cmd
from fuzzytail.cli.watch import watch_cmd

app = cyclopts.App(
    name="fuzzytail",
    help="Follow COPR build logs in your terminal.",
    version_flags=["--version", "-V"],
)

console = Console()

app.command(watch_cmd, name="watch")
app.command(logs_cmd, name="logs")
app.command(builds_cmd, name="builds")


@app.default
def default_command(
    project: Annotated[
        str,
        cyclopts.Parameter(help="COPR project in 'owner/project'"),
    ],
    *,
    package: Annotated[
        Optional[str],
        cyclopts.Parameter(
            ["--package", "-p"],
            help="Filter by package name",
        ),
    ] = None,
    chroot: Annotated[
        Optional[str],
        cyclopts.Parameter(
            ["--chroot", "-c"],
            help="Filter by chroot (e.g., 'fedora-43-x86_64')",
        ),
    ] = None,
    build_id: Annotated[
        Optional[int],
        cyclopts.Parameter(
            ["--build", "-b"],
            help="Watch a specific build ID",
        ),
    ] = None,
    srpm_only: Annotated[
        bool,
        cyclopts.Parameter(
            ["--srpm-only"],
            help="Only show SRPM build logs",
        ),
    ] = False,
    rpm_only: Annotated[
        bool,
        cyclopts.Parameter(
            ["--rpm-only"],
            help="Only show RPM build logs",
        ),
    ] = False,
    builder_live: Annotated[
        bool,
        cyclopts.Parameter(
            ["--builder-live", "-l"],
            help="Only show builder-live logs",
        ),
    ] = False,
    backend: Annotated[
        bool,
        cyclopts.Parameter(
            ["--backend", "-B"],
            help="Only show backend logs",
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
    poll_interval: Annotated[
        float,
        cyclopts.Parameter(
            ["--interval", "-i"],
            help="Poll interval in seconds",
        ),
    ] = 2.0,
) -> None:
    """Watch COPR build logs for a project.

    The default command streams logs for active builds in the specified project.
    If no active builds are found, it will wait for new builds to start.

    Examples:
        fuzzytail owner/project
        fuzzytail owner/project --package broot
        fuzzytail owner/project --chroot fedora-43-x86_64
        fuzzytail owner/project --build 12345678
    """
    from fuzzytail.models import BuildLogType
    from fuzzytail.services.copr import CoprService, CoprError
    from fuzzytail.ui.display import LogDisplay

    # Parse project
    if "/" not in project:
        console.print("[red]Error: Project must be in 'owner/project' format[/red]")
        raise SystemExit(1)

    owner, project_name = project.split("/", 1)

    # Determine log type filters
    log_types = None
    if skip_backend or (builder_live and not backend):
        log_types = [BuildLogType.BUILDER_LIVE]
    elif backend and not builder_live:
        log_types = [BuildLogType.BACKEND]

    # Determine source filters
    show_srpm = not rpm_only
    show_rpm = not srpm_only

    # Chroot filter
    chroots = [chroot] if chroot else None

    # Create display
    display = LogDisplay(
        console=console,
        show_import=not skip_import,
        show_srpm=show_srpm,
        show_rpm=show_rpm,
        log_types=log_types,
        chroots=chroots,
    )

    try:
        with CoprService() as copr:
            if build_id:
                # Watch specific build
                build = copr.get_build(build_id)
                console.print(f"[bold]Streaming logs for build #{build_id}...[/bold]\n")
                display.stream_build(build, poll_interval=poll_interval)
            else:
                # Watch project for builds
                display.watch_project(
                    owner,
                    project_name,
                    package=package,
                    poll_interval=poll_interval,
                )
    except CoprError as e:
        console.print(f"[red]COPR Error: {e}[/red]")
        raise SystemExit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow]")
