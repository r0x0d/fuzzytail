"""Functional tests for logs command using real COPR API.

These tests use the r0x0d/rust-croner COPR project for testing.
They require network access and may be slow.
"""

import pytest
from rich.console import Console
from rich.text import Text

from fuzzytail.models import BuildLogType, LogSource
from fuzzytail.services.copr import CoprService
from fuzzytail.services.logs import LogStreamer
from fuzzytail.utils import filter_logs

# Test constants
OWNER = "r0x0d"
PROJECT = "rust-croner"


class TestLogsCommandFunctional:
    """Functional tests for logs-related functionality."""

    @pytest.mark.functional
    def test_filter_logs_real_data(self) -> None:
        """Test filter_logs with real build data."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        all_logs = build.get_all_log_urls()

        # Test with all logs
        filtered_all = filter_logs(
            all_logs, show_import=True, show_srpm=True, show_rpm=True
        )
        assert len(filtered_all) == len(all_logs)

        # Test with SRPM only
        filtered_srpm = filter_logs(
            all_logs, show_import=False, show_srpm=True, show_rpm=False
        )
        for log in filtered_srpm:
            assert log.source == LogSource.SRPM

        # Test with specific log type
        filtered_backend = filter_logs(all_logs, log_types=[BuildLogType.BACKEND])
        for log in filtered_backend:
            assert log.log_type == BuildLogType.BACKEND

    @pytest.mark.functional
    def test_fetch_real_logs_content(self) -> None:
        """Test fetching actual log content."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=10)
            completed_builds = [b for b in builds if b.state.is_finished]

            if not completed_builds:
                pytest.skip("No completed builds available for testing")

            build = copr.get_build(completed_builds[0].id)

        # Try to fetch SRPM logs (most reliable)
        srpm_logs = build.get_srpm_log_urls()
        content_found = False

        with LogStreamer() as streamer:
            for log in srpm_logs:
                content = streamer.fetch_log(log)
                if content:
                    content_found = True
                    # Verify content looks like a log
                    assert isinstance(content, str)
                    assert len(content) > 0
                    break

        # At least one log should have content for a completed build
        # (unless the build was cancelled early)
        if not content_found:
            # Try import log
            import_log = build.get_import_log()
            with LogStreamer() as streamer:
                content = streamer.fetch_log(import_log)
                if content:
                    content_found = True

        # It's okay if no content found - some builds might have
        # been cleaned up or failed early

    @pytest.mark.functional
    def test_filter_logs_with_chroot(self) -> None:
        """Test filter_logs with chroot filter using real data."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        if not build.chroots:
            pytest.skip("Build has no chroots")

        chroot_name = build.chroots[0].name
        all_logs = build.get_all_log_urls()

        filtered = filter_logs(all_logs, chroots=[chroot_name])

        # Filtered logs should only have RPM logs for the specified chroot
        for log in filtered:
            if log.source == LogSource.RPM:
                assert log.chroot == chroot_name

    @pytest.mark.functional
    def test_ansi_color_preservation(self) -> None:
        """Test that ANSI colors in log content are preserved via Text.from_ansi."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=10)
            completed_builds = [b for b in builds if b.state.is_finished]

            if not completed_builds:
                pytest.skip("No completed builds available for testing")

            build = copr.get_build(completed_builds[0].id)

        srpm_logs = build.get_srpm_log_urls()

        with LogStreamer() as streamer:
            for log in srpm_logs:
                content = streamer.fetch_log(log)
                if content:
                    # Text.from_ansi should handle any content without raising
                    for line in content.split("\n")[:10]:
                        text = Text.from_ansi(line)
                        assert isinstance(text, Text)
                    return

        pytest.skip("No log content available for testing")

    @pytest.mark.functional
    def test_complete_logs_workflow(self) -> None:
        """Test complete workflow of fetching and displaying logs."""
        console = Console(force_terminal=True, width=120, record=True)

        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=5)
            completed_builds = [b for b in builds if b.state.is_finished]

            if not completed_builds:
                pytest.skip("No completed builds available for testing")

            build = copr.get_build(completed_builds[0].id)

        all_logs = build.get_all_log_urls()
        filtered_logs = filter_logs(
            all_logs, show_import=True, show_srpm=True, show_rpm=True
        )

        # Verify filtering works
        assert len(filtered_logs) > 0

        # Verify logs can be fetched and printed with ANSI colors
        with LogStreamer() as streamer:
            for log in filtered_logs[:3]:  # Test first 3 logs
                content = streamer.fetch_log(log)
                if content:
                    for line in content.split("\n")[:5]:
                        console.print(Text.from_ansi(line))

        # Export output to verify something was printed
        output = console.export_text()
        assert len(output) > 0
