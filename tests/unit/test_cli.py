"""Unit tests for fuzzytail CLI commands."""

import pytest
from pytest_mock import MockerFixture

from fuzzytail.models import Build, BuildChroot, BuildState


class TestBuildsCmd:
    """Tests for builds command."""

    @pytest.mark.unit
    def test_builds_cmd_invalid_project_format(self, mocker: MockerFixture) -> None:
        """Test builds_cmd rejects invalid project format."""
        from fuzzytail.cli.builds import builds_cmd

        mocker.patch("fuzzytail.cli.builds.console")

        with pytest.raises(SystemExit) as exc_info:
            builds_cmd("invalid_project")

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_builds_cmd_success(self, mocker: MockerFixture) -> None:
        """Test builds_cmd with valid project."""
        from fuzzytail.cli.builds import builds_cmd

        mocker.patch("fuzzytail.cli.builds.console")
        mock_copr_class = mocker.patch("fuzzytail.cli.builds.CoprService")
        mock_list_builds = mocker.patch("fuzzytail.cli.builds.list_builds")

        # Create mock builds
        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_project_builds.return_value = [mock_build]
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        builds_cmd("testowner/testproject")

        mock_copr.get_project_builds.assert_called_once_with(
            "testowner",
            "testproject",
            package=None,
            status=None,
            limit=10,
        )
        mock_list_builds.assert_called_once()

    @pytest.mark.unit
    def test_builds_cmd_no_builds(self, mocker: MockerFixture) -> None:
        """Test builds_cmd when no builds found."""
        from fuzzytail.cli.builds import builds_cmd

        mock_console = mocker.patch("fuzzytail.cli.builds.console")
        mock_copr_class = mocker.patch("fuzzytail.cli.builds.CoprService")

        mock_copr = mocker.MagicMock()
        mock_copr.get_project_builds.return_value = []
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        builds_cmd("testowner/testproject")

        # Should print "No builds found" message
        mock_console.print.assert_called()
        call_args = str(mock_console.print.call_args)
        assert "No builds found" in call_args

    @pytest.mark.unit
    def test_builds_cmd_verbose(self, mocker: MockerFixture) -> None:
        """Test builds_cmd with verbose flag."""
        from fuzzytail.cli.builds import builds_cmd

        mock_console = mocker.patch("fuzzytail.cli.builds.console")
        mock_copr_class = mocker.patch("fuzzytail.cli.builds.CoprService")
        mocker.patch("fuzzytail.ui.panels.BuildPanel")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_project_builds.return_value = [mock_build]
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        builds_cmd("testowner/testproject", verbose=True)

        # Verify panel was rendered
        mock_console.print.assert_called()

    @pytest.mark.unit
    def test_builds_cmd_with_filters(self, mocker: MockerFixture) -> None:
        """Test builds_cmd with package and status filters."""
        from fuzzytail.cli.builds import builds_cmd

        mocker.patch("fuzzytail.cli.builds.console")
        mock_copr_class = mocker.patch("fuzzytail.cli.builds.CoprService")
        mocker.patch("fuzzytail.cli.builds.list_builds")

        mock_copr = mocker.MagicMock()
        mock_copr.get_project_builds.return_value = []
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        builds_cmd(
            "testowner/testproject",
            package="mypackage",
            status="running",
            limit=5,
        )

        mock_copr.get_project_builds.assert_called_once_with(
            "testowner",
            "testproject",
            package="mypackage",
            status="running",
            limit=5,
        )

    @pytest.mark.unit
    def test_builds_cmd_copr_error(self, mocker: MockerFixture) -> None:
        """Test builds_cmd handles CoprError."""
        from fuzzytail.cli.builds import builds_cmd
        from fuzzytail.services.copr import CoprError

        mocker.patch("fuzzytail.cli.builds.console")
        mock_copr_class = mocker.patch("fuzzytail.cli.builds.CoprService")

        mock_copr = mocker.MagicMock()
        mock_copr.get_project_builds.side_effect = CoprError("API Error")
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        with pytest.raises(SystemExit) as exc_info:
            builds_cmd("testowner/testproject")

        assert exc_info.value.code == 1


class TestLogsCmd:
    """Tests for logs command."""

    @pytest.mark.unit
    def test_logs_cmd_invalid_project_format(self, mocker: MockerFixture) -> None:
        """Test logs_cmd rejects invalid project format."""
        from fuzzytail.cli.logs import logs_cmd

        mocker.patch("fuzzytail.cli.logs.console")

        with pytest.raises(SystemExit) as exc_info:
            logs_cmd("invalid_project")

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_logs_cmd_invalid_log_type(self, mocker: MockerFixture) -> None:
        """Test logs_cmd rejects invalid log type."""
        from fuzzytail.cli.logs import logs_cmd

        mocker.patch("fuzzytail.cli.logs.console")
        # CoprService is imported inside the function, so patch at source
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_copr = mocker.MagicMock()
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        with pytest.raises(SystemExit) as exc_info:
            logs_cmd("testowner/testproject", log_type="invalid")

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_logs_cmd_with_build_id(self, mocker: MockerFixture) -> None:
        """Test logs_cmd with specific build ID."""
        from fuzzytail.cli.logs import logs_cmd

        mocker.patch("fuzzytail.cli.logs.console")
        # CoprService is imported inside the function, so patch at source
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[
                BuildChroot(
                    name="fedora-43-x86_64",
                    state=BuildState.SUCCEEDED,
                    result_url="http://example.com/results",
                )
            ],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = mock_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display._filter_logs.return_value = []
        mock_display_class.return_value = mock_display

        logs_cmd("testowner/testproject", build_id=12345)

        mock_copr.get_build.assert_called_once_with(12345)

    @pytest.mark.unit
    def test_logs_cmd_no_builds(self, mocker: MockerFixture) -> None:
        """Test logs_cmd when no builds found."""
        from fuzzytail.cli.logs import logs_cmd

        mock_console = mocker.patch("fuzzytail.cli.logs.console")
        # CoprService is imported inside the function, so patch at source
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_copr = mocker.MagicMock()
        mock_copr.get_project_builds.return_value = []
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        logs_cmd("testowner/testproject")

        # Should print "No builds found" message
        mock_console.print.assert_called()

    @pytest.mark.unit
    def test_logs_cmd_skip_backend(self, mocker: MockerFixture) -> None:
        """Test logs_cmd with skip_backend flag."""
        from fuzzytail.cli.logs import logs_cmd
        from fuzzytail.models import BuildLogType

        mocker.patch("fuzzytail.cli.logs.console")
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = mock_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display._filter_logs.return_value = []
        mock_display_class.return_value = mock_display

        logs_cmd("testowner/testproject", build_id=12345, skip_backend=True)

        call_kwargs = mock_display_class.call_args.kwargs
        assert call_kwargs["log_types"] == [BuildLogType.BUILDER_LIVE]

    @pytest.mark.unit
    def test_logs_cmd_single_build_auto_select(self, mocker: MockerFixture) -> None:
        """Test logs_cmd auto-selects when only one build found."""
        from fuzzytail.cli.logs import logs_cmd

        mock_console = mocker.patch("fuzzytail.cli.logs.console")
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            package_name="testpackage",
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_project_builds.return_value = [mock_build]
        mock_copr.get_build.return_value = mock_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display._filter_logs.return_value = []
        mock_display_class.return_value = mock_display

        logs_cmd("testowner/testproject")

        # Should auto-select the single build
        mock_copr.get_build.assert_called_with(12345)
        # Should print the "Using build" message
        assert any(
            "Using build" in str(call) for call in mock_console.print.call_args_list
        )

    @pytest.mark.unit
    def test_logs_cmd_follow_mode(self, mocker: MockerFixture) -> None:
        """Test logs_cmd with follow flag."""
        from fuzzytail.cli.logs import logs_cmd

        mock_console = mocker.patch("fuzzytail.cli.logs.console")
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.RUNNING,
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = mock_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display_class.return_value = mock_display

        logs_cmd("testowner/testproject", build_id=12345, follow=True)

        # Should call stream_build in follow mode
        mock_display.stream_build.assert_called_once()
        assert any(
            "Following logs" in str(call) for call in mock_console.print.call_args_list
        )

    @pytest.mark.unit
    def test_logs_cmd_copr_error(self, mocker: MockerFixture) -> None:
        """Test logs_cmd handles CoprError."""
        from fuzzytail.cli.logs import logs_cmd
        from fuzzytail.services.copr import CoprError

        mocker.patch("fuzzytail.cli.logs.console")
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.side_effect = CoprError("API Error")
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        with pytest.raises(SystemExit) as exc_info:
            logs_cmd("testowner/testproject", build_id=12345)

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_logs_cmd_keyboard_interrupt(self, mocker: MockerFixture) -> None:
        """Test logs_cmd handles KeyboardInterrupt."""
        from fuzzytail.cli.logs import logs_cmd

        mocker.patch("fuzzytail.cli.logs.console")
        mock_copr_class = mocker.patch("fuzzytail.services.copr.CoprService")
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.RUNNING,
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = mock_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display.stream_build.side_effect = KeyboardInterrupt()
        mock_display_class.return_value = mock_display

        # Should not raise, just print message
        logs_cmd("testowner/testproject", build_id=12345, follow=True)


class TestSelectBuild:
    """Tests for _select_build function."""

    @pytest.mark.unit
    def test_select_build_user_selects(self, mocker: MockerFixture) -> None:
        """Test _select_build when user makes selection."""
        from fuzzytail.cli.logs import _select_build

        mocker.patch("fuzzytail.cli.logs.console")
        mock_prompt = mocker.patch("fuzzytail.cli.logs.IntPrompt.ask")
        mock_prompt.return_value = 1

        mock_build1 = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            package_name="pkg1",
            chroots=[],
        )
        mock_build2 = Build(
            id=12346,
            owner="testowner",
            project="testproject",
            state=BuildState.RUNNING,
            package_name="pkg2",
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = mock_build1

        result = _select_build([mock_build1, mock_build2], mock_copr)

        assert result == mock_build1
        mock_copr.get_build.assert_called_once_with(12345)

    @pytest.mark.unit
    def test_select_build_keyboard_interrupt(self, mocker: MockerFixture) -> None:
        """Test _select_build when user cancels with Ctrl+C."""
        from fuzzytail.cli.logs import _select_build

        mocker.patch("fuzzytail.cli.logs.console")
        mock_prompt = mocker.patch("fuzzytail.cli.logs.IntPrompt.ask")
        mock_prompt.side_effect = KeyboardInterrupt()

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[],
        )

        mock_copr = mocker.MagicMock()

        result = _select_build([mock_build], mock_copr)

        assert result is None

    @pytest.mark.unit
    def test_select_build_shows_table(self, mocker: MockerFixture) -> None:
        """Test _select_build displays table with build info."""
        from fuzzytail.cli.logs import _select_build

        mock_console = mocker.patch("fuzzytail.cli.logs.console")
        mock_prompt = mocker.patch("fuzzytail.cli.logs.IntPrompt.ask")
        mock_prompt.return_value = 1

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            package_name="testpackage",
            chroots=[
                BuildChroot(name="fedora-43-x86_64", state=BuildState.SUCCEEDED),
                BuildChroot(name="fedora-42-x86_64", state=BuildState.SUCCEEDED),
                BuildChroot(name="fedora-41-x86_64", state=BuildState.SUCCEEDED),
            ],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = mock_build

        _select_build([mock_build], mock_copr)

        # Should print table
        assert mock_console.print.called


class TestDisplayCompleteLogs:
    """Tests for _display_complete_logs function."""

    @pytest.mark.unit
    def test_display_complete_logs(self, mocker: MockerFixture) -> None:
        """Test _display_complete_logs fetches and displays logs."""
        from fuzzytail.cli.logs import _display_complete_logs
        from fuzzytail.models import BuildLog, BuildLogType, LogSource

        mock_console = mocker.patch("fuzzytail.cli.logs.console")
        mock_streamer_class = mocker.patch("fuzzytail.services.logs.LogStreamer")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[
                BuildChroot(
                    name="fedora-43-x86_64",
                    state=BuildState.SUCCEEDED,
                    result_url="http://example.com/results",
                )
            ],
        )

        mock_log = BuildLog(
            build_id=12345,
            log_type=BuildLogType.BACKEND,
            source=LogSource.SRPM,
            url="http://example.com/log",
        )

        mock_display = mocker.MagicMock()
        mock_display._filter_logs.return_value = [mock_log]
        mock_display._format_log_header.return_value = "Header"

        mock_streamer = mocker.MagicMock()
        mock_streamer.fetch_log.return_value = "Log content here"
        mock_streamer.__enter__ = mocker.MagicMock(return_value=mock_streamer)
        mock_streamer.__exit__ = mocker.MagicMock(return_value=None)
        mock_streamer_class.return_value = mock_streamer

        _display_complete_logs(mock_build, mock_display, None)

        mock_streamer.fetch_log.assert_called_once_with(mock_log)
        assert mock_console.print.called

    @pytest.mark.unit
    def test_display_complete_logs_no_matching_logs(
        self, mocker: MockerFixture
    ) -> None:
        """Test _display_complete_logs when no logs match filters."""
        from fuzzytail.cli.logs import _display_complete_logs

        mock_console = mocker.patch("fuzzytail.cli.logs.console")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[],
        )

        mock_display = mocker.MagicMock()
        mock_display._filter_logs.return_value = []

        _display_complete_logs(mock_build, mock_display, None)

        # Should print "No logs match" message
        assert any(
            "No logs match" in str(call) for call in mock_console.print.call_args_list
        )

    @pytest.mark.unit
    def test_display_complete_logs_no_content(self, mocker: MockerFixture) -> None:
        """Test _display_complete_logs when log has no content."""
        from fuzzytail.cli.logs import _display_complete_logs
        from fuzzytail.models import BuildLog, BuildLogType, LogSource

        mock_console = mocker.patch("fuzzytail.cli.logs.console")
        mock_streamer_class = mocker.patch("fuzzytail.services.logs.LogStreamer")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.SUCCEEDED,
            chroots=[],
        )

        mock_log = BuildLog(
            build_id=12345,
            log_type=BuildLogType.BACKEND,
            source=LogSource.SRPM,
            url="http://example.com/log",
        )

        mock_display = mocker.MagicMock()
        mock_display._filter_logs.return_value = [mock_log]

        mock_streamer = mocker.MagicMock()
        mock_streamer.fetch_log.return_value = None  # No content
        mock_streamer.__enter__ = mocker.MagicMock(return_value=mock_streamer)
        mock_streamer.__exit__ = mocker.MagicMock(return_value=None)
        mock_streamer_class.return_value = mock_streamer

        _display_complete_logs(mock_build, mock_display, None)

        # Should print "No content available" message
        assert any(
            "No content available" in str(call)
            for call in mock_console.print.call_args_list
        )


class TestWatchCmd:
    """Tests for watch command."""

    @pytest.mark.unit
    def test_watch_cmd_invalid_project_format(self, mocker: MockerFixture) -> None:
        """Test watch_cmd rejects invalid project format."""
        from fuzzytail.cli.watch import watch_cmd

        mocker.patch("fuzzytail.cli.watch.console")

        with pytest.raises(SystemExit) as exc_info:
            watch_cmd("invalid_project")

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_watch_cmd_determines_log_types(self, mocker: MockerFixture) -> None:
        """Test watch_cmd correctly determines log types from flags."""
        from fuzzytail.cli.watch import watch_cmd
        from fuzzytail.models import BuildLogType

        mocker.patch("fuzzytail.cli.watch.console")
        mock_display_class = mocker.patch("fuzzytail.cli.watch.LogDisplay")

        mock_display = mocker.MagicMock()
        mock_display.watch_project.side_effect = KeyboardInterrupt()
        mock_display_class.return_value = mock_display

        # Test with skip_backend (use no_tui=True to avoid TUI mode)
        try:
            watch_cmd("testowner/testproject", skip_backend=True, no_tui=True)
        except KeyboardInterrupt:
            pass

        call_kwargs = mock_display_class.call_args.kwargs
        assert BuildLogType.BUILDER_LIVE in call_kwargs["log_types"]
        assert BuildLogType.BACKEND not in call_kwargs["log_types"]

    @pytest.mark.unit
    def test_watch_cmd_backend_only(self, mocker: MockerFixture) -> None:
        """Test watch_cmd with backend only (builder_live=False)."""
        from fuzzytail.cli.watch import watch_cmd
        from fuzzytail.models import BuildLogType

        mocker.patch("fuzzytail.cli.watch.console")
        mock_display_class = mocker.patch("fuzzytail.cli.watch.LogDisplay")

        mock_display = mocker.MagicMock()
        mock_display.watch_project.side_effect = KeyboardInterrupt()
        mock_display_class.return_value = mock_display

        try:
            watch_cmd("testowner/testproject", builder_live=False, no_tui=True)
        except KeyboardInterrupt:
            pass

        call_kwargs = mock_display_class.call_args.kwargs
        assert BuildLogType.BACKEND in call_kwargs["log_types"]
        assert BuildLogType.BUILDER_LIVE not in call_kwargs["log_types"]

    @pytest.mark.unit
    def test_watch_cmd_no_log_types(self, mocker: MockerFixture) -> None:
        """Test watch_cmd with no log types selected sets None."""
        from fuzzytail.cli.watch import watch_cmd

        mocker.patch("fuzzytail.cli.watch.console")
        mock_display_class = mocker.patch("fuzzytail.cli.watch.LogDisplay")

        mock_display = mocker.MagicMock()
        mock_display.watch_project.side_effect = KeyboardInterrupt()
        mock_display_class.return_value = mock_display

        try:
            watch_cmd(
                "testowner/testproject",
                builder_live=False,
                backend=False,
                no_tui=True,
            )
        except KeyboardInterrupt:
            pass

        call_kwargs = mock_display_class.call_args.kwargs
        assert call_kwargs["log_types"] is None

    @pytest.mark.unit
    def test_watch_cmd_tui_mode(self, mocker: MockerFixture) -> None:
        """Test watch_cmd with TUI mode (default)."""
        from fuzzytail.cli.watch import watch_cmd

        mocker.patch("fuzzytail.cli.watch.console")
        mock_tui_class = mocker.patch("fuzzytail.ui.tui.FuzzytailApp")

        mock_app = mocker.MagicMock()
        mock_tui_class.return_value = mock_app

        watch_cmd("testowner/testproject")

        mock_tui_class.assert_called_once()
        mock_app.run.assert_called_once()

    @pytest.mark.unit
    def test_watch_cmd_tui_error(self, mocker: MockerFixture) -> None:
        """Test watch_cmd handles TUI errors."""
        from fuzzytail.cli.watch import watch_cmd

        mocker.patch("fuzzytail.cli.watch.console")
        mock_tui_class = mocker.patch("fuzzytail.ui.tui.FuzzytailApp")

        mock_app = mocker.MagicMock()
        mock_app.run.side_effect = Exception("TUI crashed")
        mock_tui_class.return_value = mock_app

        with pytest.raises(SystemExit) as exc_info:
            watch_cmd("testowner/testproject")

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_watch_cmd_copr_error(self, mocker: MockerFixture) -> None:
        """Test watch_cmd handles CoprError."""
        from fuzzytail.cli.watch import watch_cmd
        from fuzzytail.services.copr import CoprError

        mocker.patch("fuzzytail.cli.watch.console")
        mock_display_class = mocker.patch("fuzzytail.cli.watch.LogDisplay")

        mock_display = mocker.MagicMock()
        mock_display.watch_project.side_effect = CoprError("API Error")
        mock_display_class.return_value = mock_display

        with pytest.raises(SystemExit) as exc_info:
            watch_cmd("testowner/testproject", no_tui=True)

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_watch_cmd_keyboard_interrupt(self, mocker: MockerFixture) -> None:
        """Test watch_cmd handles KeyboardInterrupt."""
        from fuzzytail.cli.watch import watch_cmd

        mocker.patch("fuzzytail.cli.watch.console")
        mock_display_class = mocker.patch("fuzzytail.cli.watch.LogDisplay")

        mock_display = mocker.MagicMock()
        mock_display.watch_project.side_effect = KeyboardInterrupt()
        mock_display_class.return_value = mock_display

        # Should not raise, just print message
        watch_cmd("testowner/testproject", no_tui=True)


class TestDefaultCommand:
    """Tests for default command in main.py."""

    @pytest.mark.unit
    def test_default_command_invalid_project(self, mocker: MockerFixture) -> None:
        """Test default command rejects invalid project format."""
        from fuzzytail.cli.main import default_command

        mocker.patch("fuzzytail.cli.main.console")

        with pytest.raises(SystemExit) as exc_info:
            default_command("invalid_project")

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_default_command_with_build_id(self, mocker: MockerFixture) -> None:
        """Test default command with specific build ID."""
        from fuzzytail.cli.main import default_command

        mocker.patch("fuzzytail.cli.main.console")
        mock_copr_class = mocker.patch(
            "fuzzytail.services.copr.CoprService", autospec=True
        )
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_build = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.RUNNING,
            chroots=[],
        )

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = mock_build
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display_class.return_value = mock_display

        default_command("testowner/testproject", build_id=12345, no_tui=True)

        mock_copr.get_build.assert_called_once_with(12345)
        mock_display.stream_build.assert_called_once()

    @pytest.mark.unit
    def test_default_command_backend_log_type(self, mocker: MockerFixture) -> None:
        """Test default command with backend only flag."""
        from fuzzytail.cli.main import default_command
        from fuzzytail.models import BuildLogType

        mocker.patch("fuzzytail.cli.main.console")
        mock_copr_class = mocker.patch(
            "fuzzytail.services.copr.CoprService", autospec=True
        )
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.return_value = Build(
            id=12345,
            owner="testowner",
            project="testproject",
            state=BuildState.RUNNING,
            chroots=[],
        )
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display_class.return_value = mock_display

        default_command(
            "testowner/testproject",
            build_id=12345,
            backend=True,
            builder_live=False,
            no_tui=True,
        )

        call_kwargs = mock_display_class.call_args.kwargs
        assert call_kwargs["log_types"] == [BuildLogType.BACKEND]

    @pytest.mark.unit
    def test_default_command_tui_mode(self, mocker: MockerFixture) -> None:
        """Test default command with TUI mode (default)."""
        from fuzzytail.cli.main import default_command

        mocker.patch("fuzzytail.cli.main.console")
        mock_tui_class = mocker.patch("fuzzytail.ui.tui.FuzzytailApp")

        mock_app = mocker.MagicMock()
        mock_tui_class.return_value = mock_app

        default_command("testowner/testproject")

        mock_tui_class.assert_called_once()
        mock_app.run.assert_called_once()

    @pytest.mark.unit
    def test_default_command_tui_error(self, mocker: MockerFixture) -> None:
        """Test default command handles TUI errors."""
        from fuzzytail.cli.main import default_command

        mocker.patch("fuzzytail.cli.main.console")
        mock_tui_class = mocker.patch("fuzzytail.ui.tui.FuzzytailApp")

        mock_app = mocker.MagicMock()
        mock_app.run.side_effect = Exception("TUI crashed")
        mock_tui_class.return_value = mock_app

        with pytest.raises(SystemExit) as exc_info:
            default_command("testowner/testproject")

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_default_command_watch_project(self, mocker: MockerFixture) -> None:
        """Test default command watches project when no build_id."""
        from fuzzytail.cli.main import default_command

        mocker.patch("fuzzytail.cli.main.console")
        mock_copr_class = mocker.patch(
            "fuzzytail.services.copr.CoprService", autospec=True
        )
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_copr = mocker.MagicMock()
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display_class.return_value = mock_display

        default_command("testowner/testproject", no_tui=True)

        mock_display.watch_project.assert_called_once()

    @pytest.mark.unit
    def test_default_command_copr_error(self, mocker: MockerFixture) -> None:
        """Test default command handles CoprError."""
        from fuzzytail.cli.main import default_command
        from fuzzytail.services.copr import CoprError

        mocker.patch("fuzzytail.cli.main.console")
        mock_copr_class = mocker.patch(
            "fuzzytail.services.copr.CoprService", autospec=True
        )
        mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_copr = mocker.MagicMock()
        mock_copr.get_build.side_effect = CoprError("API Error")
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        with pytest.raises(SystemExit) as exc_info:
            default_command("testowner/testproject", build_id=12345, no_tui=True)

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_default_command_keyboard_interrupt(self, mocker: MockerFixture) -> None:
        """Test default command handles KeyboardInterrupt."""
        from fuzzytail.cli.main import default_command

        mocker.patch("fuzzytail.cli.main.console")
        mock_copr_class = mocker.patch(
            "fuzzytail.services.copr.CoprService", autospec=True
        )
        mock_display_class = mocker.patch("fuzzytail.ui.display.LogDisplay")

        mock_copr = mocker.MagicMock()
        mock_copr.__enter__ = mocker.MagicMock(return_value=mock_copr)
        mock_copr.__exit__ = mocker.MagicMock(return_value=None)
        mock_copr_class.return_value = mock_copr

        mock_display = mocker.MagicMock()
        mock_display.watch_project.side_effect = KeyboardInterrupt()
        mock_display_class.return_value = mock_display

        # Should not raise, just print message
        default_command("testowner/testproject", no_tui=True)
