"""Display helpers for non-interactive output (e.g. build listings)."""

from rich.console import Console
from rich.table import Table
from rich.text import Text

from fuzzytail.models import Build
from fuzzytail.ui.panels import get_state_icon


def list_builds(
    builds: list[Build],
    console: Console | None = None,
) -> None:
    """List builds in a table format.

    Args:
        builds: List of builds to display.
        console: Rich Console instance.
    """
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
