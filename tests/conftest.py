"""Pytest configuration and fixtures for fuzzytail tests."""

import pytest

from fuzzytail.models import (
    Build,
    BuildChroot,
    BuildLog,
    BuildLogType,
    BuildState,
    LogSource,
)


# ============================================================================
# Model Fixtures
# ============================================================================


@pytest.fixture
def sample_chroot() -> BuildChroot:
    """Create a sample BuildChroot for testing."""
    return BuildChroot(
        name="fedora-43-x86_64",
        state=BuildState.SUCCEEDED,
        result_url="https://download.copr.fedorainfracloud.org/results/testowner/testproject/fedora-43-x86_64/00012345-testpackage",
    )


@pytest.fixture
def sample_chroot_running() -> BuildChroot:
    """Create a running BuildChroot for testing."""
    return BuildChroot(
        name="fedora-42-x86_64",
        state=BuildState.RUNNING,
        result_url="https://download.copr.fedorainfracloud.org/results/testowner/testproject/fedora-42-x86_64/00012345-testpackage",
    )


@pytest.fixture
def sample_build(sample_chroot: BuildChroot) -> Build:
    """Create a sample Build for testing."""
    return Build(
        id=12345,
        owner="testowner",
        project="testproject",
        package_name="testpackage",
        state=BuildState.SUCCEEDED,
        source_package_url="https://example.com/testpackage.src.rpm",
        chroots=[sample_chroot],
        submitted_on=1700000000,
        started_on=1700000100,
        ended_on=1700000500,
    )


@pytest.fixture
def sample_build_running(sample_chroot_running: BuildChroot) -> Build:
    """Create a running Build for testing."""
    return Build(
        id=12346,
        owner="testowner",
        project="testproject",
        package_name="testpackage",
        state=BuildState.RUNNING,
        source_package_url="https://example.com/testpackage.src.rpm",
        chroots=[sample_chroot_running],
        submitted_on=1700000000,
        started_on=1700000100,
    )


@pytest.fixture
def sample_build_log() -> BuildLog:
    """Create a sample BuildLog for testing."""
    return BuildLog(
        build_id=12345,
        log_type=BuildLogType.BUILDER_LIVE,
        source=LogSource.SRPM,
        url="https://download.copr.fedorainfracloud.org/results/testowner/testproject/srpm-builds/00012345/builder-live.log",
        is_live=False,
    )


@pytest.fixture
def sample_import_log() -> BuildLog:
    """Create a sample import BuildLog for testing."""
    return BuildLog(
        build_id=12345,
        log_type=BuildLogType.IMPORT,
        source=LogSource.IMPORT,
        url="https://copr-dist-git.fedorainfracloud.org/per-task-logs/12345.log",
        is_live=False,
    )


@pytest.fixture
def sample_rpm_log() -> BuildLog:
    """Create a sample RPM BuildLog for testing."""
    return BuildLog(
        build_id=12345,
        log_type=BuildLogType.BACKEND,
        source=LogSource.RPM,
        chroot="fedora-43-x86_64",
        package_name="testpackage",
        url="https://download.copr.fedorainfracloud.org/results/testowner/testproject/fedora-43-x86_64/00012345-testpackage/backend.log",
        is_live=False,
    )


# ============================================================================
# API Response Fixtures
# ============================================================================


@pytest.fixture
def mock_build_response() -> dict:
    """Mock API response for a single build."""
    return {
        "id": 12345,
        "ownername": "testowner",
        "projectname": "testproject",
        "state": "succeeded",
        "source_package": {
            "name": "testpackage",
            "url": "https://example.com/testpackage.src.rpm",
        },
        "chroots": ["fedora-43-x86_64", "fedora-42-x86_64"],
        "submitted_on": 1700000000,
        "started_on": 1700000100,
        "ended_on": 1700000500,
    }


@pytest.fixture
def mock_builds_list_response() -> dict:
    """Mock API response for builds list."""
    return {
        "items": [
            {
                "id": 12345,
                "ownername": "testowner",
                "projectname": "testproject",
                "state": "succeeded",
                "source_package": {
                    "name": "testpackage",
                    "url": "https://example.com/testpackage.src.rpm",
                },
                "chroots": ["fedora-43-x86_64"],
                "submitted_on": 1700000000,
                "started_on": 1700000100,
                "ended_on": 1700000500,
            },
            {
                "id": 12344,
                "ownername": "testowner",
                "projectname": "testproject",
                "state": "running",
                "source_package": {
                    "name": "testpackage2",
                    "url": "https://example.com/testpackage2.src.rpm",
                },
                "chroots": ["fedora-43-x86_64", "fedora-42-x86_64"],
                "submitted_on": 1699999900,
                "started_on": 1699999950,
            },
        ]
    }


@pytest.fixture
def mock_chroots_response() -> dict:
    """Mock API response for build chroots."""
    return {
        "items": [
            {
                "name": "fedora-43-x86_64",
                "state": "succeeded",
                "result_url": "https://download.copr.fedorainfracloud.org/results/testowner/testproject/fedora-43-x86_64/00012345-testpackage",
            },
            {
                "name": "fedora-42-x86_64",
                "state": "succeeded",
                "result_url": "https://download.copr.fedorainfracloud.org/results/testowner/testproject/fedora-42-x86_64/00012345-testpackage",
            },
        ]
    }


# ============================================================================
# Constants for Functional Tests
# ============================================================================


# Use r0x0d/rust-croner for functional tests
FUNCTIONAL_TEST_OWNER = "r0x0d"
FUNCTIONAL_TEST_PROJECT = "rust-croner"
