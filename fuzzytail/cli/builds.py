"""Builds command for listing project builds."""

from typing import Annotated, Optional

import cyclopts
from rich.console import Console

from fuzzytail.services.copr import CoprError, CoprService
from fuzzytail.ui.display import list_builds

console = Console()


def builds_cmd(
    project: Annotated[
        str,
        cyclopts.Parameter(help="COPR project in 'owner/project' format"),
    ],
    *,
    package: Annotated[
        Optional[str],
        cyclopts.Parameter(
            ["--package", "-p"],
            help="Filter by package name",
        ),
    ] = None,
    status: Annotated[
        Optional[str],
        cyclopts.Parameter(
            ["--status", "-s"],
            help="Filter by status (running, pending, succeeded, failed)",
        ),
    ] = None,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            ["--limit", "-n"],
            help="Maximum number of builds to show",
        ),
    ] = 10,
    verbose: Annotated[
        bool,
        cyclopts.Parameter(
            ["--verbose", "-v"],
            help="Show detailed build information",
        ),
    ] = False,
) -> None:
    """List builds for a COPR project.

    This command shows recent builds for the specified project. Use filters
    to narrow down the results.

    Examples:
        fuzzytail builds owner/project
        fuzzytail builds owner/project --status running
        fuzzytail builds owner/project --package broot --limit 5
    """
    if "/" not in project:
        console.print("[red]Error: Project must be in 'owner/project' format[/red]")
        raise SystemExit(1)

    owner, project_name = project.split("/", 1)

    try:
        with CoprService() as copr:
            builds = copr.get_project_builds(
                owner,
                project_name,
                package=package,
                status=status,
                limit=limit,
            )

            if not builds:
                console.print("[yellow]No builds found.[/yellow]")
                return

            if verbose:
                from fuzzytail.ui.panels import BuildPanel

                for build in builds:
                    panel = BuildPanel(build)
                    console.print(panel.render())
                    console.print()
            else:
                list_builds(builds, console)

    except CoprError as e:
        console.print(f"[red]COPR Error: {e}[/red]")
        raise SystemExit(1)
