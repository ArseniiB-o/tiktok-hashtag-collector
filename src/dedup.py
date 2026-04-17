from __future__ import annotations

import sys
import threading
from collections.abc import Iterable

from src.models import VideoRecord


class DedupStore:
    """Thread-safe in-memory deduplication store for video IDs."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._lock: threading.Lock = threading.Lock()
        self._total_loaded: int = 0
        self._total_seen: int = 0

    def load(self, video_ids: Iterable[str]) -> None:
        """Load existing video IDs into the store (e.g., from persistent storage).

        Acquires the lock, filters out empty strings, adds new IDs to _seen,
        and updates counters accordingly.
        """
        with self._lock:
            before = len(self._seen)
            for vid in video_ids:
                if vid and vid.strip():
                    self._seen.add(vid.strip())
            newly_added = len(self._seen) - before
            self._total_loaded += newly_added
            self._total_seen = len(self._seen)

    def is_new(self, video_id: str) -> bool:
        """Return True if video_id has not been seen before.

        Thread-safe check against the internal set.
        """
        with self._lock:
            return video_id not in self._seen

    def mark_seen(self, video_id: str) -> None:
        """Mark a video_id as seen, incrementing _total_seen only if it was new.

        Thread-safe. Uses add pattern with length check to detect novelty.
        """
        with self._lock:
            before = len(self._seen)
            self._seen.add(video_id)
            if len(self._seen) > before:
                self._total_seen += 1

    def filter_new(self, records: list[VideoRecord]) -> list[VideoRecord]:
        """Return only records whose video_id is not in _seen.

        Acquires the lock for the entire filter operation.
        Does NOT call mark_seen — caller is responsible for that after a
        successful write.
        """
        with self._lock:
            return [r for r in records if r.video_id not in self._seen]

    @property
    def stats(self) -> dict[str, int]:
        """Return a snapshot of deduplication statistics and memory usage.

        Keys:
            total_loaded  – IDs added via load()
            total_seen    – all IDs currently in the store
            total_new     – IDs discovered after initial load
            memory_bytes  – approximate memory used by the internal set
        """
        with self._lock:
            return {
                "total_loaded": self._total_loaded,
                "total_seen": self._total_seen,
                "total_new": self._total_seen - self._total_loaded,
                "memory_bytes": sys.getsizeof(self._seen)
                + sum(sys.getsizeof(vid) for vid in self._seen),
            }

    def __len__(self) -> int:
        """Return the number of unique video IDs currently tracked. Thread-safe."""
        with self._lock:
            return len(self._seen)

    def clear(self) -> None:
        """Clear all stored IDs and reset all counters. Thread-safe. Used in tests."""
        with self._lock:
            self._seen.clear()
            self._total_loaded = 0
            self._total_seen = 0
