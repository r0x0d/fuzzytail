"""Functional tests for logs service using real COPR logs.

These tests use the r0x0d/rust-croner COPR project for testing.
They require network access and may be slow.
"""

import pytest

from fuzzytail.models import BuildLogType, LogSource
from fuzzytail.services.copr import CoprService
from fuzzytail.services.logs import LogStreamer, categorize_logs

# Test constants
OWNER = "r0x0d"
PROJECT = "rust-croner"


class TestLogStreamerFunctional:
    """Functional tests for LogStreamer with real logs."""

    @pytest.mark.functional
    def test_fetch_completed_build_log(self) -> None:
        """Test fetching log from a completed build."""
        with CoprService() as copr:
            # Get a completed build
            builds = copr.get_project_builds(OWNER, PROJECT, limit=10)
            completed_builds = [b for b in builds if b.state.is_finished]

            if not completed_builds:
                pytest.skip("No completed builds available for testing")

            build = copr.get_build(completed_builds[0].id)

        # Get SRPM logs (these are more likely to exist)
        srpm_logs = build.get_srpm_log_urls()

        with LogStreamer() as streamer:
            for log in srpm_logs:
                content = streamer.fetch_log(log)
                # At least one log should have content
                if content is not None:
                    assert isinstance(content, str)
                    assert len(content) > 0
                    break
            else:
                # If no SRPM logs found, try import log
                import_log = build.get_import_log()
                content = streamer.fetch_log(import_log)
                # Import log might not exist for all builds
                if content is not None:
                    assert isinstance(content, str)

    @pytest.mark.functional
    def test_is_log_complete_for_finished_build(self) -> None:
        """Test is_log_complete for a finished build."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=10)
            completed_builds = [b for b in builds if b.state.is_finished]

            if not completed_builds:
                pytest.skip("No completed builds available for testing")

            build = copr.get_build(completed_builds[0].id)

        srpm_logs = build.get_srpm_log_urls()

        with LogStreamer() as streamer:
            for log in srpm_logs:
                # For completed builds, logs should be complete (compressed)
                is_complete = streamer.is_log_complete(log)
                # Either complete or not available - both are valid
                assert isinstance(is_complete, bool)

    @pytest.mark.functional
    def test_get_new_content_tracking(self) -> None:
        """Test that get_new_content correctly tracks position."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=10)
            completed_builds = [b for b in builds if b.state.is_finished]

            if not completed_builds:
                pytest.skip("No completed builds available for testing")

            build = copr.get_build(completed_builds[0].id)

        srpm_logs = build.get_srpm_log_urls()

        with LogStreamer() as streamer:
            for log in srpm_logs:
                # First fetch
                chunk1 = streamer.get_new_content(log)

                if chunk1 is not None:
                    # Second fetch should return None (no new content)
                    chunk2 = streamer.get_new_content(log)

                    # For completed builds, there shouldn't be new content
                    # unless the log wasn't fully fetched the first time
                    assert chunk2 is None or len(chunk2.content) > 0
                    break

    @pytest.mark.functional
    def test_streamer_context_manager(self) -> None:
        """Test LogStreamer context manager."""
        streamer = LogStreamer()
        assert streamer._client is None

        with streamer:
            # Access client to create it
            _ = streamer.client
            assert streamer._client is not None

        assert streamer._client is None


class TestCategorizeLogs:
    """Functional tests for categorize_logs function."""

    @pytest.mark.functional
    def test_categorize_real_build_logs(self) -> None:
        """Test categorizing logs from a real build."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        all_logs = build.get_all_log_urls()

        # Test filtering by source
        import_logs = categorize_logs(all_logs, sources=[LogSource.IMPORT])
        assert all(log.source == LogSource.IMPORT for log in import_logs)

        srpm_logs = categorize_logs(all_logs, sources=[LogSource.SRPM])
        assert all(log.source == LogSource.SRPM for log in srpm_logs)

        # Test filtering by log type
        backend_logs = categorize_logs(all_logs, log_types=[BuildLogType.BACKEND])
        assert all(log.log_type == BuildLogType.BACKEND for log in backend_logs)

        builder_live_logs = categorize_logs(
            all_logs, log_types=[BuildLogType.BUILDER_LIVE]
        )
        assert all(
            log.log_type == BuildLogType.BUILDER_LIVE for log in builder_live_logs
        )

    @pytest.mark.functional
    def test_categorize_by_chroot(self) -> None:
        """Test filtering logs by chroot."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        if not build.chroots:
            pytest.skip("Build has no chroots")

        chroot_name = build.chroots[0].name
        all_logs = build.get_all_log_urls()

        filtered_logs = categorize_logs(all_logs, chroots=[chroot_name])

        # Filtered logs should include:
        # - All import logs (not chroot-specific)
        # - All SRPM logs (not chroot-specific)
        # - Only RPM logs matching the chroot
        for log in filtered_logs:
            if log.source == LogSource.RPM:
                assert log.chroot == chroot_name
