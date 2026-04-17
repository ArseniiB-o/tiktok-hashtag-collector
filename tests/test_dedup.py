"""Tests for src/dedup.py (Section R2-B)."""

from __future__ import annotations

import threading

from src.dedup import DedupStore
from src.models import VideoRecord
from src.utils import utcnow_naive


def _make_record(video_id: str) -> VideoRecord:
    return VideoRecord(
        video_id=video_id,
        url=f"https://www.tiktok.com/@u/video/{video_id}",
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
        source_hashtag="test",
        language="",
        region="",
    )


class TestDedupStore:
    def test_load_populates_seen(self) -> None:
        store = DedupStore()
        store.load(["111", "222", "333"])
        assert not store.is_new("111")
        assert not store.is_new("222")
        assert not store.is_new("333")

    def test_is_new_returns_true_for_unknown_id(self) -> None:
        store = DedupStore()
        assert store.is_new("nonexistent_id")

    def test_is_new_returns_false_for_loaded_id(self) -> None:
        store = DedupStore()
        store.load(["existing"])
        assert not store.is_new("existing")

    def test_mark_seen_causes_is_new_to_return_false(self) -> None:
        store = DedupStore()
        assert store.is_new("fresh_id")
        store.mark_seen("fresh_id")
        assert not store.is_new("fresh_id")

    def test_filter_new_returns_only_unseen(self) -> None:
        store = DedupStore()
        store.load(["111", "222"])
        records = [_make_record("111"), _make_record("222"), _make_record("333")]
        new_records = store.filter_new(records)
        assert len(new_records) == 1
        assert new_records[0].video_id == "333"

    def test_filter_new_does_not_mark_seen(self) -> None:
        store = DedupStore()
        records = [_make_record("aaa")]
        store.filter_new(records)
        # Should still be "new" since filter_new doesn't call mark_seen
        assert store.is_new("aaa")

    def test_load_is_idempotent(self) -> None:
        store = DedupStore()
        store.load(["x", "y"])
        store.load(["x", "y", "z"])
        assert len(store) == 3

    def test_stats_total_loaded(self) -> None:
        store = DedupStore()
        store.load(["a", "b", "c"])
        s = store.stats
        assert s["total_loaded"] == 3

    def test_stats_total_new(self) -> None:
        store = DedupStore()
        store.load(["a", "b"])
        store.mark_seen("c")
        s = store.stats
        assert s["total_new"] == 1

    def test_len(self) -> None:
        store = DedupStore()
        store.load(["1", "2", "3"])
        assert len(store) == 3

    def test_clear_resets_state(self) -> None:
        store = DedupStore()
        store.load(["x", "y"])
        store.clear()
        assert len(store) == 0
        assert store.is_new("x")

    def test_thread_safety_concurrent_mark_seen(self) -> None:
        """Concurrent mark_seen calls must not corrupt state."""
        store = DedupStore()
        ids = [str(i) for i in range(1000)]
        errors: list[Exception] = []

        def worker(batch: list[str]) -> None:
            try:
                for vid in batch:
                    store.mark_seen(vid)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(ids[i::4],)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(store) == 1000

    def test_empty_ids_not_loaded(self) -> None:
        """Empty string IDs should not be stored."""
        store = DedupStore()
        store.load(["", "  ", "valid"])
        assert len(store) == 1
        assert not store.is_new("valid")
