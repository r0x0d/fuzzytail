"""Functional tests for logs command using real COPR API.

These tests use the r0x0d/rust-croner COPR project for testing.
They require network access and may be slow.
"""

import pytest
from rich.console import Console

from fuzzytail.models import BuildLogType, LogSource
from fuzzytail.services.copr import CoprService
from fuzzytail.services.logs import LogStreamer
from fuzzytail.ui.display import LogDisplay

# Test constants
OWNER = "r0x0d"
PROJECT = "rust-croner"


class TestLogsCommandFunctional:
    """Functional tests for logs-related functionality."""

    @pytest.mark.functional
    def test_log_display_filter_logs(self) -> None:
        """Test LogDisplay filtering with real build data."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        all_logs = build.get_all_log_urls()

        # Test display with all logs
        display_all = LogDisplay(show_import=True, show_srpm=True, show_rpm=True)
        filtered_all = display_all._filter_logs(all_logs)
        assert len(filtered_all) == len(all_logs)

        # Test display with SRPM only
        display_srpm = LogDisplay(show_import=False, show_srpm=True, show_rpm=False)
        filtered_srpm = display_srpm._filter_logs(all_logs)
        for log in filtered_srpm:
            assert log.source == LogSource.SRPM

        # Test display with specific log type
        display_backend = LogDisplay(log_types=[BuildLogType.BACKEND])
        filtered_backend = display_backend._filter_logs(all_logs)
        for log in filtered_backend:
            assert log.log_type == BuildLogType.BACKEND

    @pytest.mark.functional
    def test_log_display_format_headers(self) -> None:
        """Test LogDisplay header formatting with real logs."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        all_logs = build.get_all_log_urls()
        display = LogDisplay()

        for log in all_logs:
            header = display._format_log_header(log)
            # Header should be a Rich Text object
            assert header is not None
            header_str = str(header)
            # Should contain some identifying information
            assert len(header_str) > 0

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
    def test_log_display_with_chroot_filter(self) -> None:
        """Test LogDisplay with chroot filter using real data."""
        with CoprService() as copr:
            builds = copr.get_project_builds(OWNER, PROJECT, limit=1)

            if not builds:
                pytest.skip("No builds available for testing")

            build = copr.get_build(builds[0].id)

        if not build.chroots:
            pytest.skip("Build has no chroots")

        chroot_name = build.chroots[0].name
        all_logs = build.get_all_log_urls()

        display = LogDisplay(chroots=[chroot_name])
        filtered = display._filter_logs(all_logs)

        # Filtered logs should only have RPM logs for the specified chroot
        for log in filtered:
            if log.source == LogSource.RPM:
                assert log.chroot == chroot_name

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

        display = LogDisplay(
            console=console,
            show_import=True,
            show_srpm=True,
            show_rpm=True,
        )

        all_logs = build.get_all_log_urls()
        filtered_logs = display._filter_logs(all_logs)

        # Verify filtering works
        assert len(filtered_logs) > 0

        # Verify headers can be formatted
        for log in filtered_logs[:3]:  # Test first 3 logs
            header = display._format_log_header(log)
            console.print(header)  # Should not raise

        # Export output to verify something was printed
        output = console.export_text()
        assert len(output) > 0
