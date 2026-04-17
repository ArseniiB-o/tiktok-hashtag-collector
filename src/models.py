"""Data models for tiktok-hashtag-collector.

Defines VideoRecord, ScraperStats, and MonitorJobStatus dataclasses used
throughout the scraping pipeline.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIKTOK_BASE_URL: str = "https://www.tiktok.com"
TIKTOK_VIDEO_URL_PREFIX: str = f"{TIKTOK_BASE_URL}/"
UNKNOWN_LANGUAGE: str = "unknown"


def _utcnow_naive() -> datetime:
    """Return a naive UTC datetime (tz-stripped). Replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_from_timestamp(ts: int) -> datetime:
    """Return a naive UTC datetime from a Unix timestamp. Replaces deprecated utcfromtimestamp()."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# VideoRecord
# ---------------------------------------------------------------------------


@dataclass
class VideoRecord:
    """Represents a single TikTok video with all metadata required for analysis."""

    video_id: str
    url: str
    description: str
    author_username: str
    author_display_name: str
    author_followers: int
    author_verified: bool
    likes: int
    comments: int
    shares: int
    views: int
    bookmarks: int
    duration_seconds: int
    created_at: datetime
    scraped_at: datetime
    hashtags: list[str]
    music_id: str
    music_title: str
    music_author: str
    source_hashtag: str
    language: str
    region: str

    def __post_init__(self) -> None:
        """Validate required fields after initialisation."""
        if not isinstance(self.video_id, str) or not self.video_id:
            raise ValueError(
                f"video_id must be a non-empty string, got: {self.video_id!r}"
            )
        if self.url and not self.url.startswith(TIKTOK_VIDEO_URL_PREFIX):
            raise ValueError(
                f"url must start with '{TIKTOK_VIDEO_URL_PREFIX}' or be empty, "
                f"got: {self.url!r}"
            )

    def to_dict(self) -> dict:
        """Return a flat dict suitable for use in a pandas DataFrame.

        - ``hashtags`` is serialised as a JSON array string.
        - ``created_at`` / ``scraped_at`` are ISO 8601 strings.
        - ``author_verified`` is the string ``"True"`` or ``"False"``.
        """
        return {
            "video_id": self.video_id,
            "url": self.url,
            "description": self.description,
            "author_username": self.author_username,
            "author_display_name": self.author_display_name,
            "author_followers": self.author_followers,
            "author_verified": str(self.author_verified),
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "views": self.views,
            "bookmarks": self.bookmarks,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.isoformat(),
            "scraped_at": self.scraped_at.isoformat(),
            "hashtags": json.dumps(self.hashtags),
            "music_id": self.music_id,
            "music_title": self.music_title,
            "music_author": self.music_author,
            "source_hashtag": self.source_hashtag,
            "language": self.language,
            "region": self.region,
        }

    @classmethod
    def from_tiktok_response(
        cls, raw: dict, source_hashtag: str
    ) -> "VideoRecord":
        """Parse a raw TikTok API response dict into a VideoRecord.

        All field access is safe — missing keys fall back to sensible defaults
        so that no KeyError or AttributeError is ever raised.

        Args:
            raw: Raw dict from the TikTok API response.
            source_hashtag: The hashtag query that produced this result.

        Returns:
            A fully populated VideoRecord instance.
        """
        stats: dict = raw.get("stats", {}) or {}
        author_info: dict = raw.get("author", {}) or {}
        music_info: dict = raw.get("music", {}) or {}

        video_id: str = str(raw.get("id", "") or "") or f"unknown-{uuid.uuid4().hex[:12]}"
        username: str = str(author_info.get("uniqueId", "") or "")

        url: str = (
            f"{TIKTOK_BASE_URL}/@{username}/video/{video_id}"
            if username and video_id
            else ""
        )

        # Resolve follower count from two possible locations in the API payload
        author_stats: dict = raw.get("authorStats", {}) or {}
        nested_stats: dict = author_info.get("stats", {}) or {}
        author_followers: int = int(
            author_stats.get("followerCount")
            or nested_stats.get("followerCount")
            or 0
        )

        # Build created_at from unix timestamp (0 → utcnow fallback)
        create_time_raw = raw.get("createTime", 0) or 0
        try:
            create_time_int: int = int(create_time_raw)
            created_at: datetime = (
                _utc_from_timestamp(create_time_int)
                if create_time_int
                else _utcnow_naive()
            )
        except (ValueError, TypeError, OSError):
            created_at = _utcnow_naive()

        # Extract hashtags from "challenges" list
        challenges: list[dict] = raw.get("challenges", []) or []
        hashtags: list[str] = [
            str(c.get("title", "") or "")
            for c in challenges
            if isinstance(c, dict) and c.get("title")
        ]

        language: str = str(
            raw.get("desc_language") or raw.get("language") or UNKNOWN_LANGUAGE
        )
        region: str = str(raw.get("regionCode") or raw.get("region") or "")

        return cls(
            video_id=video_id,
            url=url,
            description=str(raw.get("desc", "") or ""),
            author_username=username,
            author_display_name=str(author_info.get("nickname", "") or ""),
            author_followers=author_followers,
            author_verified=bool(author_info.get("verified", False)),
            likes=int(stats.get("diggCount", 0) or 0),
            comments=int(stats.get("commentCount", 0) or 0),
            shares=int(stats.get("shareCount", 0) or 0),
            views=int(stats.get("playCount", 0) or 0),
            bookmarks=int(stats.get("collectCount", 0) or 0),
            duration_seconds=int(
                (raw.get("video", {}) or {}).get("duration", 0) or 0
            ),
            created_at=created_at,
            scraped_at=_utcnow_naive(),
            hashtags=hashtags,
            music_id=str(music_info.get("id", "") or ""),
            music_title=str(music_info.get("title", "") or ""),
            music_author=str(music_info.get("authorName", "") or ""),
            source_hashtag=source_hashtag,
            language=language,
            region=region,
        )


# ---------------------------------------------------------------------------
# ScraperStats
# ---------------------------------------------------------------------------


@dataclass
class ScraperStats:
    """Tracks runtime statistics for a single hashtag scraping job."""

    hashtag: str
    started_at: datetime
    finished_at: datetime | None = None
    total_fetched: int = 0
    new_records: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    rate_limits_hit: int = 0


# ---------------------------------------------------------------------------
# MonitorJobStatus
# ---------------------------------------------------------------------------


@dataclass
class MonitorJobStatus:
    """Represents the live status of a recurring hashtag monitor job."""

    hashtag: str
    job_id: str
    interval_minutes: int
    last_run: datetime | None = None
    next_run: datetime | None = None
    is_running: bool = False
    total_records_this_session: int = 0
    last_run_new_records: int = 0
    last_run_error: str | None = None
