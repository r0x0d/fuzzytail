"""Unit tests for fuzzytail UI panels."""

import pytest

from fuzzytail.models import Build, BuildState
from fuzzytail.ui.panels import (
    BuildPanel,
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
