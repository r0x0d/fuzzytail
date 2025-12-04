"""Functional tests for COPR service using real API.

These tests use the r0x0d/rust-croner COPR project for testing.
They require network access and may be slow.
"""

import pytest

from fuzzytail.models import Build, BuildChroot, BuildState
from fuzzytail.services.copr import CoprError, CoprService

# Test constants
OWNER = "r0x0d"
PROJECT = "rust-croner"


class TestCoprServiceFunctional:
    """Functional tests for CoprService with real API calls."""

    @pytest.mark.functional
    def test_get_project_builds(self) -> None:
        """Test fetching builds from a real COPR project."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=5)

        assert len(builds) > 0
        assert len(builds) <= 5

        # Verify build structure
        for build in builds:
            assert isinstance(build, Build)
            assert build.id > 0
            assert build.owner == OWNER
            assert build.project == PROJECT
            assert isinstance(build.state, BuildState)

    @pytest.mark.functional
    def test_get_project_builds_with_limit(self) -> None:
        """Test fetching builds with specific limit."""
        with CoprService() as copr:
            builds_5 = copr.get_project_builds(OWNER, PROJECT, limit=5)
            builds_2 = copr.get_project_builds(OWNER, PROJECT, limit=2)

        assert len(builds_2) <= 2
        assert len(builds_5) <= 5

    @pytest.mark.functional
    def test_get_single_build(self) -> None:
        """Test fetching a single build by ID."""
        with CoprService() as copr:
            # First get a build ID from the project
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)
            assert len(builds) > 0

            build_id = builds[0].id

            # Now fetch the full build details
            build = copr.get_build(build_id)

        assert isinstance(build, Build)
        assert build.id == build_id
        assert build.owner == OWNER
        assert build.project == PROJECT

        # Verify chroots are populated
        assert isinstance(build.chroots, list)

    @pytest.mark.functional
    def test_get_build_with_chroots(self) -> None:
        """Test that build includes chroot information."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)
            assert len(builds) > 0

            build = copr.get_build(builds[0].id)

        # Build should have chroots (unless project has none)
        if build.chroots:
            for chroot in build.chroots:
                assert isinstance(chroot, BuildChroot)
                assert chroot.name  # Should have a name like "fedora-43-x86_64"
                assert isinstance(chroot.state, BuildState)

    @pytest.mark.functional
    def test_get_nonexistent_build(self) -> None:
        """Test that fetching nonexistent build raises CoprError."""
        with CoprService() as copr:
            # Use an impossibly high build ID
            with pytest.raises(CoprError):
                copr.get_build(999999999)

    @pytest.mark.functional
    def test_get_project_builds_nonexistent_project(self) -> None:
        """Test that fetching from nonexistent project raises CoprError."""
        with CoprService() as copr:
            with pytest.raises(CoprError):
                copr.get_project_builds(
                    "nonexistent_user_12345", "nonexistent_project_67890"
                )

    @pytest.mark.functional
    def test_build_properties(self) -> None:
        """Test that build properties are correctly populated."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)
            assert len(builds) > 0
            build = copr.get_build(builds[0].id)

        # Test base_url
        assert build.base_url.startswith("https://download.copr.fedorainfracloud.org")
        assert OWNER in build.base_url
        assert PROJECT in build.base_url

        # Test import_log_url
        assert build.import_log_url.startswith(
            "https://copr-dist-git.fedorainfracloud.org"
        )
        assert str(build.id) in build.import_log_url

    @pytest.mark.functional
    def test_build_log_urls(self) -> None:
        """Test that build log URLs are correctly generated."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)
            assert len(builds) > 0
            build = copr.get_build(builds[0].id)

        # Test import log
        import_log = build.get_import_log()
        assert import_log.build_id == build.id
        assert import_log.url == build.import_log_url

        # Test SRPM logs
        srpm_logs = build.get_srpm_log_urls()
        assert len(srpm_logs) == 2  # backend and builder-live

        # Test all logs
        all_logs = build.get_all_log_urls()
        assert len(all_logs) >= 3  # At least import + 2 SRPM logs

    @pytest.mark.functional
    def test_build_state_properties(self) -> None:
        """Test build state properties with real data."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=10)

        # Find a finished build
        finished_builds = [b for b in builds if b.state.is_finished]
        if finished_builds:
            build = finished_builds[0]
            assert build.is_active is False
            assert build.state.is_finished is True

    @pytest.mark.functional
    def test_context_manager(self) -> None:
        """Test that context manager properly manages HTTP client."""
        service = CoprService()

        # Before entering context, client should be None
        assert service._client is None

        with service as copr:
            # After using client, it should exist
            _ = copr.client
            assert service._client is not None

        # After exiting context, client should be None
        assert service._client is None

    @pytest.mark.functional
    def test_custom_timeout(self) -> None:
        """Test service with custom timeout."""
        with CoprService(timeout=60.0) as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

        assert len(builds) > 0
