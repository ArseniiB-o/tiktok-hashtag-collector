"""Tests for src/models.py (Section R2-A)."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.models import MonitorJobStatus, ScraperStats, VideoRecord
from src.utils import utcnow_naive

# --- Fixtures ---


@pytest.fixture()
def minimal_raw() -> dict:
    """Minimal raw TikTok API response with only required fields."""
    return {
        "id": "7289347823947823947",
        "author": {"uniqueId": "testuser", "nickname": "Test User"},
        "stats": {
            "diggCount": 100,
            "commentCount": 5,
            "shareCount": 2,
            "playCount": 1000,
            "collectCount": 10,
        },
        "desc": "Test video #cats",
        "createTime": 1705276800,  # 2024-01-15 00:00:00 UTC
        "music": {"id": "123", "title": "Test Song", "authorName": "Test Artist"},
        "video": {"duration": 30},
    }


@pytest.fixture()
def full_record() -> VideoRecord:
    """Fully populated VideoRecord."""
    return VideoRecord(
        video_id="7289347823947823947",
        url="https://www.tiktok.com/@testuser/video/7289347823947823947",
        description="Test video #cats",
        author_username="testuser",
        author_display_name="Test User",
        author_followers=1000,
        author_verified=False,
        likes=100,
        comments=5,
        shares=2,
        views=1000,
        bookmarks=10,
        duration_seconds=30,
        created_at=datetime(2024, 1, 15),
        scraped_at=datetime(2024, 1, 15, 9, 0, 0),
        hashtags=["cats", "funny"],
        music_id="123",
        music_title="Test Song",
        music_author="Test Artist",
        source_hashtag="cats",
        language="en",
        region="US",
    )


# --- VideoRecord construction ---


class TestVideoRecordConstruction:
    def test_full_construction(self, full_record: VideoRecord) -> None:
        assert full_record.video_id == "7289347823947823947"
        assert full_record.author_username == "testuser"
        assert full_record.likes == 100

    def test_post_init_rejects_empty_video_id(self) -> None:
        with pytest.raises(ValueError, match="video_id"):
            VideoRecord(
                video_id="",
                url="https://www.tiktok.com/@u/video/1",
                description="",
                author_username="u",
                author_display_name="",
                author_followers=0,
                author_verified=False,
                likes=0,
                comments=0,
                shares=0,
                views=0,
                bookmarks=0,
                duration_seconds=0,
                created_at=utcnow_naive(),
                scraped_at=utcnow_naive(),
                hashtags=[],
                music_id="",
                music_title="",
                music_author="",
                source_hashtag="",
                language="",
                region="",
            )

    def test_post_init_rejects_invalid_url(self) -> None:
        with pytest.raises(ValueError, match="url"):
            VideoRecord(
                video_id="123",
                url="http://evil.com/video/123",
                description="",
                author_username="u",
                author_display_name="",
                author_followers=0,
                author_verified=False,
                likes=0,
                comments=0,
                shares=0,
                views=0,
                bookmarks=0,
                duration_seconds=0,
                created_at=utcnow_naive(),
                scraped_at=utcnow_naive(),
                hashtags=[],
                music_id="",
                music_title="",
                music_author="",
                source_hashtag="",
                language="",
                region="",
            )

    def test_post_init_allows_empty_url(self, full_record: VideoRecord) -> None:
        """Empty URL is allowed (when username not available)."""
        r = VideoRecord(
            video_id="123",
            url="",
            description="",
            author_username="",
            author_display_name="",
            author_followers=0,
            author_verified=False,
            likes=0,
            comments=0,
            shares=0,
            views=0,
            bookmarks=0,
            duration_seconds=0,
            created_at=utcnow_naive(),
            scraped_at=utcnow_naive(),
            hashtags=[],
            music_id="",
            music_title="",
            music_author="",
            source_hashtag="",
            language="",
            region="",
        )
        assert r.url == ""


# --- to_dict ---


class TestVideoRecordToDict:
    def test_produces_flat_dict(self, full_record: VideoRecord) -> None:
        d = full_record.to_dict()
        assert isinstance(d, dict)
        assert d["video_id"] == "7289347823947823947"

    def test_hashtags_as_json_string(self, full_record: VideoRecord) -> None:
        d = full_record.to_dict()
        parsed = json.loads(d["hashtags"])
        assert parsed == ["cats", "funny"]

    def test_author_verified_as_string(self, full_record: VideoRecord) -> None:
        d = full_record.to_dict()
        assert d["author_verified"] in ("True", "False")

    def test_datetimes_as_iso_strings(self, full_record: VideoRecord) -> None:
        d = full_record.to_dict()
        # Should be parseable ISO strings
        datetime.fromisoformat(d["created_at"])
        datetime.fromisoformat(d["scraped_at"])


# --- from_tiktok_response ---


class TestVideoRecordFromResponse:
    def test_parses_minimal_raw(self, minimal_raw: dict) -> None:
        record = VideoRecord.from_tiktok_response(minimal_raw, "cats")
        assert record.video_id == "7289347823947823947"
        assert record.author_username == "testuser"
        assert record.source_hashtag == "cats"

    def test_parses_stats(self, minimal_raw: dict) -> None:
        record = VideoRecord.from_tiktok_response(minimal_raw, "cats")
        assert record.likes == 100
        assert record.comments == 5
        assert record.shares == 2
        assert record.views == 1000
        assert record.bookmarks == 10

    def test_parses_music(self, minimal_raw: dict) -> None:
        record = VideoRecord.from_tiktok_response(minimal_raw, "cats")
        assert record.music_id == "123"
        assert record.music_title == "Test Song"
        assert record.music_author == "Test Artist"

    def test_constructs_url(self, minimal_raw: dict) -> None:
        record = VideoRecord.from_tiktok_response(minimal_raw, "cats")
        assert "testuser" in record.url
        assert "7289347823947823947" in record.url

    def test_handles_missing_stats(self) -> None:
        record = VideoRecord.from_tiktok_response({"id": "999"}, "test")
        assert record.video_id == "999"
        assert record.likes == 0
        assert record.views == 0
        assert record.hashtags == []

    def test_handles_empty_dict(self) -> None:
        """Should not crash on empty dict."""
        record = VideoRecord.from_tiktok_response({}, "test")
        assert isinstance(record, VideoRecord)
        assert isinstance(record.created_at, datetime)

    def test_parses_challenges_as_hashtags(self) -> None:
        raw = {
            "id": "111",
            "challenges": [{"title": "cats"}, {"title": "viral"}, {"title": "funny"}],
        }
        record = VideoRecord.from_tiktok_response(raw, "cats")
        assert "cats" in record.hashtags
        assert "viral" in record.hashtags


# --- ScraperStats ---


class TestScraperStats:
    def test_default_values(self) -> None:
        stats = ScraperStats(hashtag="cats", started_at=utcnow_naive())
        assert stats.total_fetched == 0
        assert stats.new_records == 0
        assert stats.finished_at is None


# --- MonitorJobStatus ---


class TestMonitorJobStatus:
    def test_default_values(self) -> None:
        status = MonitorJobStatus(hashtag="cats", job_id="abc", interval_minutes=15)
        assert status.is_running is False
        assert status.total_records_this_session == 0
        assert status.last_run is None
