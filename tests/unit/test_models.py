"""Unit tests for fuzzytail models."""

import pytest

from fuzzytail.models import (
    Build,
    BuildChroot,
    BuildLog,
    BuildLogType,
    BuildState,
    LogSource,
)


class TestBuildState:
    """Tests for BuildState enum."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "state,expected",
        [
            (BuildState.IMPORTING, True),
            (BuildState.PENDING, True),
            (BuildState.STARTING, True),
            (BuildState.RUNNING, True),
            (BuildState.WAITING, True),
            (BuildState.SUCCEEDED, False),
            (BuildState.FORKED, False),
            (BuildState.SKIPPED, False),
            (BuildState.FAILED, False),
            (BuildState.CANCELED, False),
        ],
    )
    def test_is_active(self, state: BuildState, expected: bool) -> None:
        """Test that is_active returns correct value for each state."""
        assert state.is_active == expected

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "state,expected",
        [
            (BuildState.IMPORTING, False),
            (BuildState.PENDING, False),
            (BuildState.STARTING, False),
            (BuildState.RUNNING, False),
            (BuildState.WAITING, False),
            (BuildState.SUCCEEDED, True),
            (BuildState.FORKED, True),
            (BuildState.SKIPPED, True),
            (BuildState.FAILED, True),
            (BuildState.CANCELED, True),
        ],
    )
    def test_is_finished(self, state: BuildState, expected: bool) -> None:
        """Test that is_finished returns correct value for each state."""
        assert state.is_finished == expected

    @pytest.mark.unit
    def test_state_values(self) -> None:
        """Test that state values match expected strings."""
        assert BuildState.IMPORTING.value == "importing"
        assert BuildState.RUNNING.value == "running"
        assert BuildState.SUCCEEDED.value == "succeeded"
        assert BuildState.FAILED.value == "failed"


class TestBuildLogType:
    """Tests for BuildLogType enum."""

    @pytest.mark.unit
    def test_log_type_values(self) -> None:
        """Test that log type values match expected strings."""
        assert BuildLogType.IMPORT.value == "import"
        assert BuildLogType.BACKEND.value == "backend"
        assert BuildLogType.BUILDER_LIVE.value == "builder-live"


class TestLogSource:
    """Tests for LogSource enum."""

    @pytest.mark.unit
    def test_log_source_values(self) -> None:
        """Test that log source values match expected strings."""
        assert LogSource.IMPORT.value == "import"
        assert LogSource.SRPM.value == "srpm"
        assert LogSource.RPM.value == "rpm"


class TestBuildLog:
    """Tests for BuildLog model."""

    @pytest.mark.unit
    def test_create_build_log(self, sample_build_log: BuildLog) -> None:
        """Test creating a BuildLog instance."""
        assert sample_build_log.build_id == 12345
        assert sample_build_log.log_type == BuildLogType.BUILDER_LIVE
        assert sample_build_log.source == LogSource.SRPM
        assert sample_build_log.is_live is False

    @pytest.mark.unit
    def test_display_name_import(self, sample_import_log: BuildLog) -> None:
        """Test display_name for import log."""
        assert sample_import_log.display_name == "[IMPORT] dist-git"

    @pytest.mark.unit
    def test_display_name_srpm(self, sample_build_log: BuildLog) -> None:
        """Test display_name for SRPM log."""
        assert sample_build_log.display_name == "[SRPM] builder-live"

    @pytest.mark.unit
    def test_display_name_rpm(self, sample_rpm_log: BuildLog) -> None:
        """Test display_name for RPM log."""
        assert sample_rpm_log.display_name == "[fedora-43-x86_64] backend"


class TestBuildChroot:
    """Tests for BuildChroot model."""

    @pytest.mark.unit
    def test_create_build_chroot(self, sample_chroot: BuildChroot) -> None:
        """Test creating a BuildChroot instance."""
        assert sample_chroot.name == "fedora-43-x86_64"
        assert sample_chroot.state == BuildState.SUCCEEDED
        assert sample_chroot.result_url is not None

    @pytest.mark.unit
    def test_create_build_chroot_without_result_url(self) -> None:
        """Test creating a BuildChroot without result_url."""
        chroot = BuildChroot(
            name="fedora-43-x86_64",
            state=BuildState.PENDING,
        )
        assert chroot.result_url is None


class TestBuild:
    """Tests for Build model."""

    @pytest.mark.unit
    def test_create_build(self, sample_build: Build) -> None:
        """Test creating a Build instance."""
        assert sample_build.id == 12345
        assert sample_build.owner == "testowner"
        assert sample_build.project == "testproject"
        assert sample_build.package_name == "testpackage"
        assert sample_build.state == BuildState.SUCCEEDED

    @pytest.mark.unit
    def test_is_active_property(
        self, sample_build: Build, sample_build_running: Build
    ) -> None:
        """Test is_active property."""
        assert sample_build.is_active is False
        assert sample_build_running.is_active is True

    @pytest.mark.unit
    def test_base_url(self, sample_build: Build) -> None:
        """Test base_url property."""
        expected = (
            "https://download.copr.fedorainfracloud.org/results/testowner/testproject"
        )
        assert sample_build.base_url == expected

    @pytest.mark.unit
    def test_import_log_url(self, sample_build: Build) -> None:
        """Test import_log_url property."""
        expected = "https://copr-dist-git.fedorainfracloud.org/per-task-logs/12345.log"
        assert sample_build.import_log_url == expected

    @pytest.mark.unit
    def test_get_import_log(self, sample_build: Build) -> None:
        """Test get_import_log method."""
        log = sample_build.get_import_log()
        assert log.build_id == sample_build.id
        assert log.log_type == BuildLogType.IMPORT
        assert log.source == LogSource.IMPORT
        assert log.url == sample_build.import_log_url

    @pytest.mark.unit
    def test_get_srpm_log_urls(self, sample_build: Build) -> None:
        """Test get_srpm_log_urls method."""
        logs = sample_build.get_srpm_log_urls()
        # Should have BACKEND and BUILDER_LIVE logs (not IMPORT)
        assert len(logs) == 2
        log_types = {log.log_type for log in logs}
        assert BuildLogType.BACKEND in log_types
        assert BuildLogType.BUILDER_LIVE in log_types
        assert BuildLogType.IMPORT not in log_types
        for log in logs:
            assert log.source == LogSource.SRPM

    @pytest.mark.unit
    def test_get_rpm_log_urls(self, sample_build: Build) -> None:
        """Test get_rpm_log_urls method."""
        logs = sample_build.get_rpm_log_urls()
        # One chroot with BACKEND and BUILDER_LIVE
        assert len(logs) == 2
        for log in logs:
            assert log.source == LogSource.RPM
            assert log.chroot == "fedora-43-x86_64"

    @pytest.mark.unit
    def test_get_rpm_log_urls_with_filter(self, sample_build: Build) -> None:
        """Test get_rpm_log_urls with chroot filter."""
        logs = sample_build.get_rpm_log_urls(chroot="nonexistent")
        assert len(logs) == 0

    @pytest.mark.unit
    def test_get_all_log_urls(self, sample_build: Build) -> None:
        """Test get_all_log_urls method."""
        logs = sample_build.get_all_log_urls()
        # Import (1) + SRPM (2) + RPM (2) = 5
        assert len(logs) == 5

        sources = {log.source for log in logs}
        assert LogSource.IMPORT in sources
        assert LogSource.SRPM in sources
        assert LogSource.RPM in sources

    @pytest.mark.unit
    def test_build_without_chroots(self) -> None:
        """Test build without any chroots."""
        build = Build(
            id=99999,
            owner="owner",
            project="project",
            state=BuildState.PENDING,
        )
        rpm_logs = build.get_rpm_log_urls()
        assert len(rpm_logs) == 0

    @pytest.mark.unit
    def test_build_with_chroot_without_result_url(self) -> None:
        """Test build with chroot that has no result_url."""
        chroot = BuildChroot(
            name="fedora-43-x86_64",
            state=BuildState.PENDING,
            result_url=None,
        )
        build = Build(
            id=99999,
            owner="owner",
            project="project",
            state=BuildState.PENDING,
            chroots=[chroot],
        )
        rpm_logs = build.get_rpm_log_urls()
        assert len(rpm_logs) == 0
