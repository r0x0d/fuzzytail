"""Functional tests for builds command using real COPR API.

These tests use the r0x0d/rust-croner COPR project for testing.
They require network access and may be slow.
"""

import pytest
from rich.console import Console

from fuzzytail.models import Build
from fuzzytail.services.copr import CoprService
from fuzzytail.ui.display import list_builds
from fuzzytail.ui.panels import BuildPanel

# Test constants
OWNER = "r0x0d"
PROJECT = "rust-croner"


class TestBuildsCommandFunctional:
    """Functional tests for builds-related functionality."""

    @pytest.mark.functional
    def test_list_builds_real_data(self) -> None:
        """Test listing builds with real data."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=5)

        assert len(builds) > 0

        # Test that list_builds doesn't raise with real data
        console = Console(force_terminal=True, width=120)
        list_builds(builds, console)  # Should not raise

    @pytest.mark.functional
    def test_build_panel_real_data(self) -> None:
        """Test BuildPanel rendering with real data."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        panel = BuildPanel(build)
        rendered = panel.render()

        # Verify panel can be rendered
        assert rendered is not None

        console = Console(force_terminal=True, width=120)
        console.print(rendered)  # Should not raise

    @pytest.mark.functional
    def test_builds_with_various_states(self) -> None:
        """Test that builds with various states are handled correctly."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=20)

        # Collect different states we found
        states_found = {build.state for build in builds}

        # We should find at least succeeded builds in a stable project
        assert len(states_found) >= 1

        # All builds should be valid
        for build in builds:
            assert isinstance(build, Build)
            assert build.id > 0
            assert build.owner == OWNER
            assert build.project == PROJECT

    @pytest.mark.functional
    def test_build_chroot_information(self) -> None:
        """Test that chroot information is correctly fetched."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            # Get full build with chroot details
            build = copr.get_build(builds[0].id)

        # rust-croner should have at least one chroot
        if build.chroots:
            chroot = build.chroots[0]
            assert chroot.name  # e.g., "fedora-43-x86_64"
            assert chroot.state  # Should have a state

            # result_url might be None for pending builds
            if build.state.is_finished and chroot.result_url:
                assert "download.copr.fedorainfracloud.org" in chroot.result_url
