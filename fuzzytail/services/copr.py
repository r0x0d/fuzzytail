"""Service for interacting with COPR API."""

import json
import subprocess
from typing import Optional

import httpx

from fuzzytail.models import Build, BuildChroot, BuildState


class CoprError(Exception):
    """Exception raised when COPR operations fail."""

    pass


class CoprService:
    """Service for fetching COPR build information."""

    COPR_API_BASE = "https://copr.fedorainfracloud.org/api_3"

    def __init__(self, timeout: float = 30.0):
        """Initialize the COPR service.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self._timeout = timeout
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "CoprService":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_build(self, build_id: int) -> Build:
        """Fetch a single build by ID with full chroot details.

        Args:
            build_id: The COPR build ID.

        Returns:
            Build object with all details.

        Raises:
            CoprError: If the build cannot be fetched.
        """
        url = f"{self.COPR_API_BASE}/build/{build_id}"

        try:
            response = self.client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise CoprError(f"Failed to fetch build {build_id}: {e}") from e
        except httpx.RequestError as e:
            raise CoprError(f"Network error fetching build {build_id}: {e}") from e

        # Fetch detailed chroot information
        chroots = self._get_build_chroots(build_id)

        return self._parse_build(data, chroots)

    def _get_build_chroots(self, build_id: int) -> list[BuildChroot]:
        """Fetch detailed chroot information for a build.

        Args:
            build_id: The COPR build ID.

        Returns:
            List of BuildChroot objects.
        """
        url = f"{self.COPR_API_BASE}/build-chroot/list"
        params = {"build_id": build_id}

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return []

        chroots = []
        for item in data.get("items", []):
            try:
                chroots.append(
                    BuildChroot(
                        name=item.get("name", ""),
                        state=BuildState(item.get("state", "pending")),
                        result_url=item.get("result_url"),
                    )
                )
            except (KeyError, ValueError):
                continue

        return chroots

    def get_project_builds(
        self,
        owner: str,
        project: str,
        package: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> list[Build]:
        """Fetch builds for a project.

        Args:
            owner: Project owner username.
            project: Project name.
            package: Optional package name filter.
            status: Optional status filter (running, pending, etc.).
            limit: Maximum number of builds to return.

        Returns:
            List of Build objects.

        Raises:
            CoprError: If builds cannot be fetched.
        """
        url = f"{self.COPR_API_BASE}/build/list"
        params: dict[str, str | int] = {
            "ownername": owner,
            "projectname": project,
            "limit": limit,
        }

        if package:
            params["packagename"] = package
        if status:
            params["status"] = status

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            raise CoprError(f"Failed to fetch builds for {owner}/{project}: {e}") from e
        except httpx.RequestError as e:
            raise CoprError(
                f"Network error fetching builds for {owner}/{project}: {e}"
            ) from e

        builds = []
        for item in data.get("items", []):
            try:
                # For list endpoint, chroots is just a list of names
                # Create basic BuildChroot objects without states
                chroot_names = item.get("chroots", [])
                chroots = [
                    BuildChroot(
                        name=name,
                        state=BuildState(item.get("state", "pending")),
                        result_url=self._build_result_url(
                            item.get("ownername", ""),
                            item.get("projectname", ""),
                            name,
                            item.get("id", 0),
                            item.get("source_package", {}).get("name", ""),
                        ),
                    )
                    for name in chroot_names
                ]
                builds.append(self._parse_build(item, chroots))
            except (KeyError, ValueError):
                # Skip malformed build entries
                continue

        return builds

    def get_running_builds(self, owner: str, project: str) -> list[Build]:
        """Get all currently running builds for a project.

        Args:
            owner: Project owner username.
            project: Project name.

        Returns:
            List of running Build objects.
        """
        return self.get_project_builds(owner, project, status="running")

    def get_pending_builds(self, owner: str, project: str) -> list[Build]:
        """Get all pending builds for a project.

        Args:
            owner: Project owner username.
            project: Project name.

        Returns:
            List of pending Build objects.
        """
        return self.get_project_builds(owner, project, status="pending")

    def _build_result_url(
        self,
        owner: str,
        project: str,
        chroot: str,
        build_id: int,
        package_name: str,
    ) -> Optional[str]:
        """Build the result URL for a chroot.

        Args:
            owner: Project owner.
            project: Project name.
            chroot: Chroot name.
            build_id: Build ID.
            package_name: Package name.

        Returns:
            Result URL or None if package name is missing.
        """
        if not package_name:
            return None
        return (
            f"https://download.copr.fedorainfracloud.org/results/"
            f"{owner}/{project}/{chroot}/{build_id:08d}-{package_name}"
        )

    def _parse_build(
        self,
        data: dict,
        chroots: Optional[list[BuildChroot]] = None,
    ) -> Build:
        """Parse raw API response into a Build object.

        Args:
            data: Raw JSON data from the API.
            chroots: Optional pre-fetched chroot information.

        Returns:
            Parsed Build object.
        """
        owner = data.get("ownername", "")
        project = data.get("projectname", "")
        build_id = data.get("id", 0)
        package_name = data.get("source_package", {}).get("name", "")

        # Use provided chroots or create empty list
        if chroots is None:
            chroots = []

        return Build(
            id=build_id,
            owner=owner,
            project=project,
            package_name=package_name or None,
            state=BuildState(data.get("state", "pending")),
            source_package_url=data.get("source_package", {}).get("url"),
            chroots=chroots,
            submitted_on=data.get("submitted_on"),
            started_on=data.get("started_on"),
            ended_on=data.get("ended_on"),
        )


def get_builds_via_cli(
    owner: str, project: str, package: Optional[str] = None
) -> list[dict]:
    """Get builds using the copr CLI tool.

    This is an alternative method when the API is not accessible or
    when we need authenticated access.

    Args:
        owner: Project owner username.
        project: Project name.
        package: Optional package name filter.

    Returns:
        List of build data dictionaries.

    Raises:
        CoprError: If the CLI command fails.
    """
    cmd = ["copr-cli", "list-builds", f"{owner}/{project}", "--output-format", "json"]

    if package:
        cmd.extend(["--packagename", package])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise CoprError(f"copr-cli failed: {e.stderr}") from e
    except json.JSONDecodeError as e:
        raise CoprError(f"Failed to parse copr-cli output: {e}") from e
    except FileNotFoundError:
        raise CoprError(
            "copr-cli not found. Install it with: dnf install copr-cli"
        ) from None
