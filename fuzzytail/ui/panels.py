"""Rich panel components for build information display."""

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from fuzzytail.models import Build, BuildState


def get_state_style(state: BuildState) -> str:
    """Get the Rich style for a build state.

    Args:
        state: The build state.

    Returns:
        Rich style string.
    """
    styles = {
        BuildState.IMPORTING: "yellow",
        BuildState.PENDING: "yellow",
        BuildState.STARTING: "cyan",
        BuildState.RUNNING: "blue bold",
        BuildState.SUCCEEDED: "green bold",
        BuildState.FORKED: "green",
        BuildState.SKIPPED: "dim",
        BuildState.FAILED: "red bold",
        BuildState.CANCELED: "red",
        BuildState.WAITING: "yellow",
    }
    return styles.get(state, "white")


def get_state_icon(state: BuildState) -> str:
    """Get an icon for a build state.

    Args:
        state: The build state.

    Returns:
        Unicode icon string.
    """
    icons = {
        BuildState.IMPORTING: "📥",
        BuildState.PENDING: "⏳",
        BuildState.STARTING: "🚀",
        BuildState.RUNNING: "🔄",
        BuildState.SUCCEEDED: "✅",
        BuildState.FORKED: "🔱",
        BuildState.SKIPPED: "⏭️",
        BuildState.FAILED: "❌",
        BuildState.CANCELED: "🚫",
        BuildState.WAITING: "⏸️",
    }
    return icons.get(state, "❓")


class BuildPanel:
    """Panel for displaying build information."""

    def __init__(self, build: Build):
        """Initialize the build panel.

        Args:
            build: The Build object to display.
        """
        self.build = build

    def render(self) -> Panel:
        """Render the build panel.

        Returns:
            Rich Panel object.
        """
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan")
        table.add_column("Value")

        state_text = Text()
        state_text.append(
            f"{get_state_icon(self.build.state)} {self.build.state.value}",
            style=get_state_style(self.build.state),
        )

        table.add_row("Build ID", str(self.build.id))
        table.add_row("Project", f"{self.build.owner}/{self.build.project}")
        if self.build.package_name:
            table.add_row("Package", self.build.package_name)
        table.add_row("State", state_text)

        if self.build.chroots:
            chroot_lines = []
            for chroot in self.build.chroots:
                icon = get_state_icon(chroot.state)
                style = get_state_style(chroot.state)
                chroot_text = Text()
                chroot_text.append(f"{icon} {chroot.name}", style=style)
                chroot_lines.append(chroot_text)

            if chroot_lines:
                table.add_row("Chroots", Group(*chroot_lines))

        return Panel(
            table,
            title=f"[bold white]🔨 Build #{self.build.id}[/bold white]",
            subtitle=f"[dim]{self.build.owner}/{self.build.project}[/dim]",
            border_style="bright_blue",
            padding=(1, 2),
        )
