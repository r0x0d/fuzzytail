"""Pydantic models for COPR build structures."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class BuildState(str, Enum):
    """Possible states of a COPR build."""

    IMPORTING = "importing"
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FORKED = "forked"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELED = "canceled"
    WAITING = "waiting"

    @property
    def is_active(self) -> bool:
        """Check if the build state indicates an active build."""
        return self in {
            BuildState.IMPORTING,
            BuildState.PENDING,
            BuildState.STARTING,
            BuildState.RUNNING,
            BuildState.WAITING,
        }

    @property
    def is_finished(self) -> bool:
        """Check if the build state indicates a finished build."""
        return self in {
            BuildState.SUCCEEDED,
            BuildState.FORKED,
            BuildState.SKIPPED,
            BuildState.FAILED,
            BuildState.CANCELED,
        }


class BuildLogType(str, Enum):
    """Types of build logs available in COPR."""

    # Import log (dist-git import)
    IMPORT = "import"
    # Backend logs (orchestration), then builder-live (actual build output)
    BACKEND = "backend"
    BUILDER_LIVE = "builder-live"


class LogSource(str, Enum):
    """Source of the log (import, SRPM build, or RPM build)."""

    IMPORT = "import"
    SRPM = "srpm"
    RPM = "rpm"


class BuildLog(BaseModel):
    """Represents a single build log file."""

    build_id: int = Field(description="The COPR build ID")
    log_type: BuildLogType = Field(description="Type of log")
    source: LogSource = Field(description="Source of log (import, srpm, or rpm)")
    chroot: Optional[str] = Field(
        default=None, description="Chroot name (only for RPM builds)"
    )
    package_name: Optional[str] = Field(
        default=None, description="Package name (only for RPM builds)"
    )
    url: str = Field(description="URL to the log file")
    is_live: bool = Field(
        default=True, description="Whether the log is still being written"
    )

    @property
    def display_name(self) -> str:
        """Get a human-readable display name for this log."""
        if self.source == LogSource.IMPORT:
            return "[IMPORT] dist-git"
        if self.source == LogSource.SRPM:
            return f"[SRPM] {self.log_type.value}"
        return f"[{self.chroot}] {self.log_type.value}"


class BuildChroot(BaseModel):
    """Represents a build chroot (architecture target)."""

    name: str = Field(description="Chroot name (e.g., fedora-43-x86_64)")
    state: BuildState = Field(description="Current state of this chroot build")
    result_url: Optional[str] = Field(
        default=None, description="URL to the build results directory"
    )


class Build(BaseModel):
    """Represents a COPR build."""

    id: int = Field(description="The COPR build ID")
    owner: str = Field(description="Owner of the COPR project")
    project: str = Field(description="COPR project name")
    package_name: Optional[str] = Field(
        default=None, description="Name of the package being built"
    )
    state: BuildState = Field(description="Current state of the build")
    source_package_url: Optional[str] = Field(
        default=None, description="URL to the source package"
    )
    chroots: list[BuildChroot] = Field(
        default_factory=list, description="List of chroot builds"
    )
    submitted_on: Optional[int] = Field(
        default=None, description="Unix timestamp when build was submitted"
    )
    started_on: Optional[int] = Field(
        default=None, description="Unix timestamp when build started"
    )
    ended_on: Optional[int] = Field(
        default=None, description="Unix timestamp when build ended"
    )

    @property
    def is_active(self) -> bool:
        """Check if the build is currently active."""
        return self.state.is_active

    @property
    def base_url(self) -> str:
        """Get the base URL for this build's logs."""
        return f"https://download.copr.fedorainfracloud.org/results/{self.owner}/{self.project}"

    @property
    def import_log_url(self) -> str:
        """Get the URL for the dist-git import log."""
        return f"https://copr-dist-git.fedorainfracloud.org/per-task-logs/{self.id}.log"

    def get_import_log(self) -> BuildLog:
        """Get the dist-git import log."""
        return BuildLog(
            build_id=self.id,
            log_type=BuildLogType.IMPORT,
            source=LogSource.IMPORT,
            url=self.import_log_url,
            is_live=self.state == BuildState.IMPORTING,
        )

    def get_srpm_log_urls(self) -> list[BuildLog]:
        """Get URLs for SRPM build logs."""
        logs = []
        base = f"{self.base_url}/srpm-builds/{self.id:08d}"

        for log_type in BuildLogType:
            # Skip import log type - it's handled separately
            if log_type == BuildLogType.IMPORT:
                continue
            logs.append(
                BuildLog(
                    build_id=self.id,
                    log_type=log_type,
                    source=LogSource.SRPM,
                    url=f"{base}/{log_type.value}.log",
                    is_live=True,
                )
            )

        return logs

    def get_rpm_log_urls(self, chroot: Optional[str] = None) -> list[BuildLog]:
        """Get URLs for RPM build logs for specified or all chroots."""
        logs = []
        target_chroots = self.chroots

        if chroot:
            target_chroots = [c for c in self.chroots if c.name == chroot]

        for build_chroot in target_chroots:
            if not build_chroot.result_url:
                continue

            for log_type in BuildLogType:
                # Skip import log type - it's handled separately
                if log_type == BuildLogType.IMPORT:
                    continue
                logs.append(
                    BuildLog(
                        build_id=self.id,
                        log_type=log_type,
                        source=LogSource.RPM,
                        chroot=build_chroot.name,
                        package_name=self.package_name,
                        url=f"{build_chroot.result_url}/{log_type.value}.log",
                        is_live=build_chroot.state.is_active,
                    )
                )

        return logs

    def get_all_log_urls(self, chroot: Optional[str] = None) -> list[BuildLog]:
        """Get all log URLs for this build, including import log."""
        return (
            [self.get_import_log()]
            + self.get_srpm_log_urls()
            + self.get_rpm_log_urls(chroot)
        )
