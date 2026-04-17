"""Utility functions for tiktok-hashtag-collector."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

TIKTOK_BASE_URL: str = "https://www.tiktok.com"
MIN_DELAY_FLOOR: float = 0.5


def utcnow_naive() -> datetime:
    """Return a naive UTC datetime. Replaces deprecated datetime.utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


def utc_from_timestamp(ts: int) -> datetime:
    """Return a naive UTC datetime from a Unix timestamp. Replaces utcfromtimestamp()."""
    return datetime.fromtimestamp(ts, tz=UTC).replace(tzinfo=None)


def normalize_hashtag(hashtag: str) -> str:
    """Normalize a hashtag string to lowercase alphanumerics and underscores.

    Strips leading '#', strips whitespace, converts to lowercase, and removes
    all characters except alphanumerics and underscores.

    Args:
        hashtag: Raw hashtag string, optionally prefixed with '#'.

    Returns:
        Normalized hashtag string without leading '#'.

    Examples:
        >>> normalize_hashtag("#Funny Cats!")
        'funnycats'
        >>> normalize_hashtag("  #hello_world  ")
        'hello_world'
    """
    stripped = hashtag.strip().lstrip("#").lower()
    return re.sub(r"[^\w]", "", stripped)


def construct_video_url(username: str, video_id: str) -> str:
    """Construct a TikTok video URL from a username and video ID.

    Args:
        username: TikTok username (without '@' prefix).
        video_id: TikTok video ID string.

    Returns:
        Full TikTok video URL.

    Examples:
        >>> construct_video_url("example_user", "7123456789")
        'https://www.tiktok.com/@example_user/video/7123456789'
    """
    return f"https://www.tiktok.com/@{username}/video/{video_id}"


def parse_tiktok_timestamp(ts: int | str | None) -> datetime:
    """Convert a TikTok timestamp to a naive UTC datetime object.

    Accepts Unix timestamps (int) or ISO 8601 strings. Never raises exceptions.

    Args:
        ts: Unix timestamp as int, ISO 8601 string, or None/falsy value.

    Returns:
        Naive UTC datetime object. Falls back to datetime.utcnow() on failure.

    Examples:
        >>> parse_tiktok_timestamp(0)  # doctest: +ELLIPSIS
        datetime.datetime(...)
        >>> parse_tiktok_timestamp(1700000000)
        datetime.datetime(2023, 11, 14, 22, 13, 20)
    """
    if not ts:
        return utcnow_naive()

    if isinstance(ts, int):
        if ts <= 0:
            return utcnow_naive()
        try:
            return utc_from_timestamp(ts)
        except (OSError, OverflowError, ValueError):
            return utcnow_naive()

    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt
        except (ValueError, AttributeError):
            return utcnow_naive()

    return utcnow_naive()


def format_large_number(n: int) -> str:
    """Format an integer into a human-readable string with K/M/B suffixes.

    Handles negative numbers correctly.

    Args:
        n: Integer to format.

    Returns:
        Formatted string with appropriate suffix.

    Examples:
        >>> format_large_number(1_500_000_000)
        '1.5B'
        >>> format_large_number(2_300_000)
        '2.3M'
        >>> format_large_number(45_000)
        '45.0K'
        >>> format_large_number(999)
        '999'
        >>> format_large_number(-1_500_000)
        '-1.5M'
    """
    abs_n = abs(n)
    sign = "-" if n < 0 else ""

    if abs_n >= 1_000_000_000:
        return f"{sign}{abs_n / 1_000_000_000:.1f}B"
    if abs_n >= 1_000_000:
        return f"{sign}{abs_n / 1_000_000:.1f}M"
    if abs_n >= 1_000:
        return f"{sign}{abs_n / 1_000:.1f}K"
    return str(n)


def safe_get(data: dict, *keys: str, default: object = None) -> object:
    """Safely traverse a nested dictionary without raising KeyError.

    Walks the dictionary using the provided keys. Returns the default if any
    key is missing or if an intermediate value is not a dict (or is None).

    Args:
        data: The root dictionary to traverse.
        *keys: Sequence of string keys representing the path to the value.
        default: Value to return if traversal fails. Defaults to None.

    Returns:
        The value at the nested path, or default if not reachable.

    Examples:
        >>> safe_get({"a": {"b": {"c": 42}}}, "a", "b", "c")
        42
        >>> safe_get({"a": 1}, "a", "b", default=0)
        0
        >>> safe_get({}, "missing", default="fallback")
        'fallback'
    """
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def create_output_dir(path: Path) -> None:
    """Create a directory and all necessary parent directories.

    Args:
        path: Path object representing the directory to create.

    Raises:
        PermissionError: If the directory cannot be created due to permissions
            or other OS-level errors, with a user-friendly message including
            the path.

    Examples:
        >>> import tempfile, os
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     create_output_dir(Path(tmp) / "new" / "nested" / "dir")
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise PermissionError(
            f"Permission denied: cannot create directory '{path}'. "
            f"Check that you have write access to this location."
        ) from exc
    except OSError as exc:
        raise PermissionError(
            f"Failed to create directory '{path}': {exc}. "
            f"Check that the path is valid and you have write access."
        ) from exc


def get_file_size_human(path: Path) -> str:
    """Return a human-readable file size string for the given path.

    Args:
        path: Path to the file whose size to read.

    Returns:
        Human-readable size string (e.g. '1.5 MB', '320.0 KB', '512 B').
        Returns '0 B' if the path does not exist or cannot be stat'd.

    Examples:
        >>> get_file_size_human(Path("/nonexistent/file.txt"))
        '0 B'
    """
    try:
        size = path.stat().st_size
    except (OSError, FileNotFoundError):
        return "0 B"

    if size >= 1_073_741_824:
        return f"{size / 1_073_741_824:.1f} GB"
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1_024:
        return f"{size / 1_024:.1f} KB"
    return f"{size} B"


def generate_session_id() -> str:
    """Generate a new unique session identifier using UUID4.

    Returns:
        A UUID4 string in standard hyphenated format.

    Examples:
        >>> import re
        >>> bool(re.match(r'^[0-9a-f-]{36}$', generate_session_id()))
        True
    """
    return str(uuid.uuid4())
