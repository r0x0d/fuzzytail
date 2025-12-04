"""Services for interacting with COPR and fetching logs."""

from fuzzytail.services.copr import CoprService
from fuzzytail.services.logs import LogStreamer

__all__ = [
    "CoprService",
    "LogStreamer",
]
