"""Unit tests for fuzzytail COPR service."""

import httpx
import pytest
from pytest_mock import MockerFixture

from fuzzytail.models import Build, BuildState
from fuzzytail.services.copr import CoprError, CoprService, get_builds_via_cli


class TestCoprService:
    """Tests for CoprService class."""

    @pytest.mark.unit
    def test_init_default_timeout(self) -> None:
        """Test default timeout initialization."""
        service = CoprService()
        assert service._timeout == 30.0
        assert service._client is None

    @pytest.mark.unit
    def test_init_custom_timeout(self) -> None:
        """Test custom timeout initialization."""
        service = CoprService(timeout=60.0)
        assert service._timeout == 60.0

    @pytest.mark.unit
    def test_client_property_creates_client(self) -> None:
        """Test that client property creates httpx.Client."""
        service = CoprService()
        try:
            client = service.client
            assert isinstance(client, httpx.Client)
            assert service._client is client
        finally:
            service.close()

    @pytest.mark.unit
    def test_close(self) -> None:
        """Test close method."""
        service = CoprService()
        _ = service.client  # Create client
        service.close()
        assert service._client is None

    @pytest.mark.unit
    def test_context_manager(self) -> None:
        """Test context manager protocol."""
        with CoprService() as service:
            _ = service.client
            assert service._client is not None
        assert service._client is None

    @pytest.mark.unit
    def test_get_build(
        self,
        mocker: MockerFixture,
        mock_build_response: dict,
        mock_chroots_response: dict,
    ) -> None:
        """Test get_build method."""
        service = CoprService()

        mock_client = mocker.MagicMock()

        # Mock HTTP responses
        mock_response_build = mocker.MagicMock()
        mock_response_build.json.return_value = mock_build_response
        mock_response_build.raise_for_status = mocker.MagicMock()

        mock_response_chroots = mocker.MagicMock()
        mock_response_chroots.json.return_value = mock_chroots_response
        mock_response_chroots.raise_for_status = mocker.MagicMock()

        mock_client.get.side_effect = [mock_response_build, mock_response_chroots]

        mocker.patch.object(service, "_client", mock_client)

        build = service.get_build(12345)

        assert isinstance(build, Build)
        assert build.id == 12345
        assert build.owner == "testowner"
        assert build.project == "testproject"
        assert build.state == BuildState.SUCCEEDED

    @pytest.mark.unit
    def test_get_build_http_error(self, mocker: MockerFixture) -> None:
        """Test get_build raises CoprError on HTTP error."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=mocker.MagicMock(), response=mocker.MagicMock()
        )
        mock_client.get.return_value = mock_response

        mocker.patch.object(service, "_client", mock_client)

        with pytest.raises(CoprError) as exc_info:
            service.get_build(99999)

        assert "Failed to fetch build" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_build_network_error(self, mocker: MockerFixture) -> None:
        """Test get_build raises CoprError on network error."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")

        mocker.patch.object(service, "_client", mock_client)

        with pytest.raises(CoprError) as exc_info:
            service.get_build(12345)

        assert "Network error" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_project_builds(
        self, mocker: MockerFixture, mock_builds_list_response: dict
    ) -> None:
        """Test get_project_builds method."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = mock_builds_list_response
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(service, "_client", mock_client)

        builds = service.get_project_builds("testowner", "testproject")

        assert len(builds) == 2
        assert builds[0].id == 12345
        assert builds[1].id == 12344

    @pytest.mark.unit
    def test_get_project_builds_with_filters(
        self, mocker: MockerFixture, mock_builds_list_response: dict
    ) -> None:
        """Test get_project_builds with package and status filters."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = mock_builds_list_response
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(service, "_client", mock_client)

        service.get_project_builds(
            "testowner",
            "testproject",
            package="testpackage",
            status="running",
            limit=5,
        )

        # Verify correct params were passed
        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params["packagename"] == "testpackage"
        assert params["status"] == "running"
        assert params["limit"] == 5

    @pytest.mark.unit
    def test_get_project_builds_http_error(self, mocker: MockerFixture) -> None:
        """Test get_project_builds raises CoprError on HTTP error."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=mocker.MagicMock(), response=mocker.MagicMock()
        )
        mock_client.get.return_value = mock_response

        mocker.patch.object(service, "_client", mock_client)

        with pytest.raises(CoprError) as exc_info:
            service.get_project_builds("testowner", "testproject")

        assert "Failed to fetch builds" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_running_builds(
        self, mocker: MockerFixture, mock_builds_list_response: dict
    ) -> None:
        """Test get_running_builds method."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = mock_builds_list_response
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(service, "_client", mock_client)

        service.get_running_builds("testowner", "testproject")

        # Verify status=running was passed
        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params["status"] == "running"

    @pytest.mark.unit
    def test_get_pending_builds(
        self, mocker: MockerFixture, mock_builds_list_response: dict
    ) -> None:
        """Test get_pending_builds method."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.json.return_value = mock_builds_list_response
        mock_response.raise_for_status = mocker.MagicMock()
        mock_client.get.return_value = mock_response

        mocker.patch.object(service, "_client", mock_client)

        service.get_pending_builds("testowner", "testproject")

        call_args = mock_client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert params["status"] == "pending"

    @pytest.mark.unit
    def test_build_result_url(self) -> None:
        """Test _build_result_url method."""
        service = CoprService()
        url = service._build_result_url(
            owner="testowner",
            project="testproject",
            chroot="fedora-43-x86_64",
            build_id=12345,
            package_name="testpackage",
        )
        expected = (
            "https://download.copr.fedorainfracloud.org/results/"
            "testowner/testproject/fedora-43-x86_64/00012345-testpackage"
        )
        assert url == expected

    @pytest.mark.unit
    def test_build_result_url_no_package(self) -> None:
        """Test _build_result_url returns None when package_name is missing."""
        service = CoprService()
        url = service._build_result_url(
            owner="testowner",
            project="testproject",
            chroot="fedora-43-x86_64",
            build_id=12345,
            package_name="",
        )
        assert url is None

    @pytest.mark.unit
    def test_parse_build(self, mock_build_response: dict) -> None:
        """Test _parse_build method."""
        service = CoprService()
        build = service._parse_build(mock_build_response)

        assert build.id == 12345
        assert build.owner == "testowner"
        assert build.project == "testproject"
        assert build.package_name == "testpackage"
        assert build.state == BuildState.SUCCEEDED

    @pytest.mark.unit
    def test_get_build_chroots_handles_errors(self, mocker: MockerFixture) -> None:
        """Test _get_build_chroots returns empty list on error."""
        service = CoprService()

        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=mocker.MagicMock(), response=mocker.MagicMock()
        )
        mock_client.get.return_value = mock_response

        mocker.patch.object(service, "_client", mock_client)

        chroots = service._get_build_chroots(12345)
        assert chroots == []


class TestGetBuildsViaCli:
    """Tests for get_builds_via_cli function."""

    @pytest.mark.unit
    def test_get_builds_via_cli_success(self, mocker: MockerFixture) -> None:
        """Test successful CLI call."""
        mock_output = '[{"id": 12345, "state": "succeeded"}]'
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(stdout=mock_output, returncode=0)

        builds = get_builds_via_cli("testowner", "testproject")

        assert len(builds) == 1
        assert builds[0]["id"] == 12345

    @pytest.mark.unit
    def test_get_builds_via_cli_with_package(self, mocker: MockerFixture) -> None:
        """Test CLI call with package filter."""
        mock_output = "[]"
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(stdout=mock_output, returncode=0)

        get_builds_via_cli("testowner", "testproject", package="testpackage")

        call_args = mock_run.call_args[0][0]
        assert "--packagename" in call_args
        assert "testpackage" in call_args

    @pytest.mark.unit
    def test_get_builds_via_cli_command_error(self, mocker: MockerFixture) -> None:
        """Test CLI call raises CoprError on command failure."""
        from subprocess import CalledProcessError

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = CalledProcessError(1, "copr-cli", stderr="Error")

        with pytest.raises(CoprError) as exc_info:
            get_builds_via_cli("testowner", "testproject")

        assert "copr-cli failed" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_builds_via_cli_json_error(self, mocker: MockerFixture) -> None:
        """Test CLI call raises CoprError on invalid JSON."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = mocker.MagicMock(stdout="invalid json", returncode=0)

        with pytest.raises(CoprError) as exc_info:
            get_builds_via_cli("testowner", "testproject")

        assert "Failed to parse" in str(exc_info.value)

    @pytest.mark.unit
    def test_get_builds_via_cli_not_found(self, mocker: MockerFixture) -> None:
        """Test CLI call raises CoprError when copr-cli is not found."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(CoprError) as exc_info:
            get_builds_via_cli("testowner", "testproject")

        assert "copr-cli not found" in str(exc_info.value)
