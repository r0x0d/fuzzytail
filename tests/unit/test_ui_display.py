"""Unit tests for fuzzytail UI display helpers."""

import pytest
from pytest_mock import MockerFixture
from rich.console import Console

from fuzzytail.models import Build
from fuzzytail.ui.display import list_builds


class TestListBuilds:
    """Tests for list_builds function."""

    @pytest.mark.unit
    def test_list_builds(self, mocker: MockerFixture, sample_build: Build) -> None:
        """Test list_builds function."""
        console = mocker.MagicMock(spec=Console)
        list_builds([sample_build], console)

        console.print.assert_called_once()

    @pytest.mark.unit
    def test_list_builds_multiple(
        self, mocker: MockerFixture, sample_build: Build, sample_build_running: Build
    ) -> None:
        """Test list_builds with multiple builds."""
        console = mocker.MagicMock(spec=Console)
        list_builds([sample_build, sample_build_running], console)

        console.print.assert_called_once()

    @pytest.mark.unit
    def test_list_builds_empty(self, mocker: MockerFixture) -> None:
        """Test list_builds with empty list."""
        console = mocker.MagicMock(spec=Console)
        list_builds([], console)

        # Should still print table (with no rows)
        console.print.assert_called_once()
