"""Shared utility functions for fuzzytail."""

import time

from fuzzytail.models import BuildLog, BuildLogType, LogSource


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds into a human-readable string.

    Args:
        seconds: Elapsed time in seconds.

    Returns:
        Formatted time string (e.g. "5s", "2m05s", "1h30m00s").
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h{mins:02d}m{secs:02d}s"


def interruptible_sleep(
    seconds: float,
    interval: float = 0.05,
    stop_condition: callable | None = None,
) -> None:
    """Sleep that can be interrupted by KeyboardInterrupt or a stop condition.

    Args:
        seconds: Total seconds to sleep.
        interval: Check interval for interrupts (default 0.05s for snappy response).
        stop_condition: Optional callable that returns True to stop early.
    """
    elapsed = 0.0
    while elapsed < seconds:
        if stop_condition and stop_condition():
            break
        time.sleep(min(interval, seconds - elapsed))
        elapsed += interval


def categorize_logs(
    logs: list[BuildLog],
    log_types: list[BuildLogType] | None = None,
    sources: list[LogSource] | None = None,
    chroots: list[str] | None = None,
) -> list[BuildLog]:
    """Filter and categorize logs based on criteria.

    Args:
        logs: List of all available logs.
        log_types: Filter by log types (import, builder-live, backend).
        sources: Filter by log sources (import, srpm, rpm).
        chroots: Filter by chroot names.

    Returns:
        Filtered list of BuildLog objects.
    """
    filtered = logs

    if log_types:
        filtered = [entry for entry in filtered if entry.log_type in log_types]

    if sources:
        filtered = [entry for entry in filtered if entry.source in sources]

    if chroots:
        # Import and SRPM logs are not chroot-specific, always include them
        filtered = [
            entry
            for entry in filtered
            if entry.source in (LogSource.IMPORT, LogSource.SRPM)
            or entry.chroot in chroots
        ]

    return filtered


def filter_logs(
    logs: list[BuildLog],
    *,
    show_import: bool = True,
    show_srpm: bool = True,
    show_rpm: bool = True,
    log_types: list[BuildLogType] | None = None,
    chroots: list[str] | None = None,
) -> list[BuildLog]:
    """Filter logs based on display settings.

    This is a convenience wrapper around ``categorize_logs`` that translates
    boolean show_* flags into source filters.

    Args:
        logs: List of all available logs.
        show_import: Whether to include import (dist-git) logs.
        show_srpm: Whether to include SRPM logs.
        show_rpm: Whether to include RPM logs.
        log_types: Specific log types to show (default: all).
        chroots: Specific chroots to filter (default: all).

    Returns:
        Filtered list of logs.
    """
    sources: list[LogSource] = []
    if show_import:
        sources.append(LogSource.IMPORT)
    if show_srpm:
        sources.append(LogSource.SRPM)
    if show_rpm:
        sources.append(LogSource.RPM)

    return categorize_logs(
        logs,
        log_types=log_types,
        sources=sources,
        chroots=chroots,
    )
