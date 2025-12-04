"""Unit tests for fuzzytail UI panels."""

import pytest

from fuzzytail.models import Build, BuildLog, BuildLogType, BuildState, LogSource
from fuzzytail.ui.panels import (
    BuildPanel,
    LogPanel,
    get_state_icon,
    get_state_style,
)


class TestGetStateStyle:
    """Tests for get_state_style function."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "state,expected",
        [
            (BuildState.IMPORTING, "yellow"),
            (BuildState.PENDING, "yellow"),
            (BuildState.STARTING, "cyan"),
            (BuildState.RUNNING, "blue bold"),
            (BuildState.SUCCEEDED, "green bold"),
            (BuildState.FORKED, "green"),
            (BuildState.SKIPPED, "dim"),
            (BuildState.FAILED, "red bold"),
            (BuildState.CANCELED, "red"),
            (BuildState.WAITING, "yellow"),
        ],
    )
    def test_get_state_style(self, state: BuildState, expected: str) -> None:
        """Test that get_state_style returns correct style for each state."""
        assert get_state_style(state) == expected


class TestGetStateIcon:
    """Tests for get_state_icon function."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "state,expected",
        [
            (BuildState.IMPORTING, "📥"),
            (BuildState.PENDING, "⏳"),
            (BuildState.STARTING, "🚀"),
            (BuildState.RUNNING, "🔄"),
            (BuildState.SUCCEEDED, "✅"),
            (BuildState.FORKED, "🔱"),
            (BuildState.SKIPPED, "⏭️"),
            (BuildState.FAILED, "❌"),
            (BuildState.CANCELED, "🚫"),
            (BuildState.WAITING, "⏸️"),
        ],
    )
    def test_get_state_icon(self, state: BuildState, expected: str) -> None:
        """Test that get_state_icon returns correct icon for each state."""
        assert get_state_icon(state) == expected


class TestBuildPanel:
    """Tests for BuildPanel class."""

    @pytest.mark.unit
    def test_create_build_panel(self, sample_build: Build) -> None:
        """Test creating a BuildPanel instance."""
        panel = BuildPanel(sample_build)
        assert panel.build == sample_build

    @pytest.mark.unit
    def test_render_returns_panel(self, sample_build: Build) -> None:
        """Test that render returns a Rich Panel."""
        from rich.panel import Panel

        panel = BuildPanel(sample_build)
        rendered = panel.render()
        assert isinstance(rendered, Panel)

    @pytest.mark.unit
    def test_render_contains_build_info(self, sample_build: Build) -> None:
        """Test that rendered panel contains build information."""
        panel = BuildPanel(sample_build)
        rendered = panel.render()

        # Check title contains build ID
        assert str(sample_build.id) in str(rendered.title)

    @pytest.mark.unit
    def test_render_build_without_package_name(self) -> None:
        """Test rendering build without package name."""
        from fuzzytail.models import BuildChroot

        build = Build(
            id=99999,
            owner="testowner",
            project="testproject",
            state=BuildState.PENDING,
            chroots=[
                BuildChroot(
                    name="fedora-43-x86_64",
                    state=BuildState.PENDING,
                )
            ],
        )
        panel = BuildPanel(build)
        # Should not raise
        rendered = panel.render()
        assert rendered is not None

    @pytest.mark.unit
    def test_render_build_without_chroots(self) -> None:
        """Test rendering build without chroots."""
        build = Build(
            id=99999,
            owner="testowner",
            project="testproject",
            state=BuildState.PENDING,
            chroots=[],
        )
        panel = BuildPanel(build)
        rendered = panel.render()
        assert rendered is not None


class TestLogPanel:
    """Tests for LogPanel class."""

    @pytest.fixture
    def sample_logs(self) -> list[BuildLog]:
        """Create sample logs for testing."""
        return [
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BACKEND,
                source=LogSource.SRPM,
                url="http://example.com/srpm-backend.log",
            ),
            BuildLog(
                build_id=1,
                log_type=BuildLogType.BUILDER_LIVE,
                source=LogSource.RPM,
                chroot="fedora-43-x86_64",
                url="http://example.com/rpm-builder-live.log",
            ),
        ]

    @pytest.mark.unit
    def test_create_log_panel(self, sample_logs: list[BuildLog]) -> None:
        """Test creating a LogPanel instance."""
        panel = LogPanel(sample_logs)
        assert panel.logs == sample_logs
        assert len(panel._active) == 0

    @pytest.mark.unit
    def test_set_active(self, sample_logs: list[BuildLog]) -> None:
        """Test set_active method."""
        panel = LogPanel(sample_logs)
        url = sample_logs[0].url

        panel.set_active(url, True)
        assert url in panel._active

        panel.set_active(url, False)
        assert url not in panel._active

    @pytest.mark.unit
    def test_render_returns_panel(self, sample_logs: list[BuildLog]) -> None:
        """Test that render returns a Rich Panel."""
        from rich.console import Console
        from rich.panel import Panel

        panel = LogPanel(sample_logs)
        console = Console()
        rendered = panel.render(console)
        assert isinstance(rendered, Panel)
