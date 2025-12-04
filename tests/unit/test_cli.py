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

        # Test with skip_backend
        try:
            watch_cmd("testowner/testproject", skip_backend=True)
        except KeyboardInterrupt:
            pass

        call_kwargs = mock_display_class.call_args.kwargs
        assert BuildLogType.BUILDER_LIVE in call_kwargs["log_types"]
        assert BuildLogType.BACKEND not in call_kwargs["log_types"]


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

        default_command("testowner/testproject", build_id=12345)

        mock_copr.get_build.assert_called_once_with(12345)
        mock_display.stream_build.assert_called_once()
