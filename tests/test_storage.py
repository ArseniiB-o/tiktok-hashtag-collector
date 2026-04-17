"""Tests for src/storage.py (Section R2-C)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import AppConfig
from src.dedup import DedupStore
from src.models import VideoRecord
from src.storage import StorageManager


def _make_config(tmp_path: Path, fmt: str = "csv") -> AppConfig:
    config = AppConfig()
    config.output_dir = tmp_path / "output"
    config.output_format = fmt
    config.write_batch_size = 5
    return config


def _make_record(video_id: str, hashtag: str = "cats") -> VideoRecord:
    return VideoRecord(
        video_id=video_id,
        url=f"https://www.tiktok.com/@user/video/{video_id}",
        description=f"Video {video_id}",
        author_username="user",
        author_display_name="User",
        author_followers=100,
        author_verified=False,
        likes=10,
        comments=2,
        shares=1,
        views=500,
        bookmarks=3,
        duration_seconds=15,
        created_at=datetime(2024, 1, 15),
        scraped_at=datetime(2024, 1, 15, 9, 0, 0),
        hashtags=[hashtag],
        music_id="m1",
        music_title="Song",
        music_author="Artist",
        source_hashtag=hashtag,
        language="en",
        region="US",
    )


class TestGetOutputPath:
    def test_returns_csv_path_for_hashtag(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        dedup = DedupStore()
        storage = StorageManager(config, dedup)
        path = storage.get_output_path("cats")
        assert "cats" in path.stem
        assert path.suffix == ".csv"

    def test_returns_xlsx_for_excel_format(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path, fmt="excel")
        storage = StorageManager(config, DedupStore())
        path = storage.get_output_path("dogs")
        assert path.suffix == ".xlsx"

    def test_combined_path_contains_combined(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        storage = StorageManager(config, DedupStore())
        path = storage.get_output_path("any", combined=True)
        assert "combined" in path.stem


class TestLoadExisting:
    def test_returns_empty_set_for_missing_file(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        storage = StorageManager(config, DedupStore())
        result = storage.load_existing("nonexistent")
        assert result == set()

    def test_reads_video_ids_from_existing_csv(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        config.output_dir.mkdir(parents=True, exist_ok=True)

        # Manually create a CSV
        from datetime import date

        today = date.today().isoformat()
        csv_path = config.output_dir / f"cats_{today}.csv"
        df = pd.DataFrame([{"video_id": "111"}, {"video_id": "222"}])
        df.to_csv(csv_path, index=False)

        storage = StorageManager(config, DedupStore())
        result = storage.load_existing("cats")
        assert "111" in result
        assert "222" in result

    def test_returns_empty_set_for_missing_video_id_column(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        config.output_dir.mkdir(parents=True, exist_ok=True)

        from datetime import date

        today = date.today().isoformat()
        csv_path = config.output_dir / f"cats_{today}.csv"
        df = pd.DataFrame([{"other_col": "val"}])
        df.to_csv(csv_path, index=False)

        storage = StorageManager(config, DedupStore())
        result = storage.load_existing("cats")
        assert result == set()


class TestWriteRecords:
    def test_creates_file_on_first_write(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        dedup = DedupStore()
        storage = StorageManager(config, dedup)
        records = [_make_record(f"{i}") for i in range(3)]

        storage.write_records(records, "cats")
        storage.flush("cats")

        output_path = storage.get_output_path("cats")
        assert output_path.exists()

    def test_write_and_read_back(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        dedup = DedupStore()
        storage = StorageManager(config, dedup)
        records = [_make_record(f"{i}") for i in range(3)]

        storage.write_records(records, "cats")
        storage.flush("cats")

        output_path = storage.get_output_path("cats")
        df = pd.read_csv(output_path, dtype=str)
        assert len(df) == 3
        assert set(df["video_id"]) == {"0", "1", "2"}

    def test_appends_on_second_write(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        dedup = DedupStore()
        storage = StorageManager(config, dedup)

        storage.write_records([_make_record("a")], "cats")
        storage.flush("cats")
        storage.write_records([_make_record("b")], "cats")
        storage.flush("cats")

        output_path = storage.get_output_path("cats")
        df = pd.read_csv(output_path, dtype=str)
        assert len(df) == 2

    def test_dedup_prevents_duplicate_writes(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        dedup = DedupStore()
        dedup.load(["dup"])
        storage = StorageManager(config, dedup)

        count = storage.write_records([_make_record("dup"), _make_record("fresh")], "cats")
        storage.flush("cats")

        assert count == 1  # only 1 new
        output_path = storage.get_output_path("cats")
        df = pd.read_csv(output_path, dtype=str)
        assert "fresh" in df["video_id"].values
        assert "dup" not in df["video_id"].values

    def test_returns_zero_when_all_duplicates(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        dedup = DedupStore()
        dedup.load(["x", "y"])
        storage = StorageManager(config, dedup)

        count = storage.write_records([_make_record("x"), _make_record("y")], "cats")
        assert count == 0

    def test_utf8_bom_encoding(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        storage = StorageManager(config, DedupStore())
        storage.write_records([_make_record("1")], "cats")
        storage.flush("cats")

        output_path = storage.get_output_path("cats")
        raw_bytes = output_path.read_bytes()
        # UTF-8 BOM is EF BB BF
        assert raw_bytes[:3] == b"\xef\xbb\xbf", "File should start with UTF-8 BOM"

    def test_written_csv_is_valid_pandas(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        storage = StorageManager(config, DedupStore())
        storage.write_records([_make_record("abc")], "cats")
        storage.flush("cats")

        output_path = storage.get_output_path("cats")
        df = pd.read_csv(output_path)
        assert "video_id" in df.columns
        assert len(df) == 1
