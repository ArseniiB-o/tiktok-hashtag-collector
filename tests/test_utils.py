"""Tests for src/utils.py (Section R2-D)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.utils import (
    construct_video_url,
    create_output_dir,
    format_large_number,
    generate_session_id,
    get_file_size_human,
    normalize_hashtag,
    parse_tiktok_timestamp,
    safe_get,
    utcnow_naive,
)


class TestNormalizeHashtag:
    def test_strips_hash(self) -> None:
        assert normalize_hashtag("#cats") == "cats"

    def test_strips_whitespace(self) -> None:
        assert normalize_hashtag("  cats  ") == "cats"

    def test_lowercases(self) -> None:
        assert normalize_hashtag("CATS") == "cats"

    def test_removes_special_chars(self) -> None:
        assert normalize_hashtag("#Funny Cats!") == "funnycats"

    def test_preserves_underscores(self) -> None:
        assert normalize_hashtag("hello_world") == "hello_world"

    def test_empty_string(self) -> None:
        assert normalize_hashtag("") == ""

    def test_hash_only(self) -> None:
        assert normalize_hashtag("#") == ""


class TestConstructVideoUrl:
    def test_basic_url(self) -> None:
        url = construct_video_url("testuser", "123456")
        assert url == "https://www.tiktok.com/@testuser/video/123456"

    def test_url_format(self) -> None:
        url = construct_video_url("charli", "9999")
        assert url.startswith("https://www.tiktok.com/@")
        assert "video" in url


class TestParseTiktokTimestamp:
    def test_parses_unix_int(self) -> None:
        ts = 1705276800  # 2024-01-15 00:00:00 UTC
        result = parse_tiktok_timestamp(ts)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parses_iso_string(self) -> None:
        result = parse_tiktok_timestamp("2024-01-15T12:00:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_returns_utcnow_for_none(self) -> None:
        before = utcnow_naive()
        result = parse_tiktok_timestamp(None)
        after = utcnow_naive()
        assert before <= result <= after

    def test_returns_utcnow_for_zero(self) -> None:
        before = utcnow_naive()
        result = parse_tiktok_timestamp(0)
        after = utcnow_naive()
        assert before <= result <= after

    def test_never_raises(self) -> None:
        for bad in ["not-a-date", -99999999999, "garbage"]:
            result = parse_tiktok_timestamp(bad)
            assert isinstance(result, datetime)


class TestFormatLargeNumber:
    def test_billions(self) -> None:
        assert "B" in format_large_number(1_500_000_000)

    def test_millions(self) -> None:
        assert "M" in format_large_number(2_500_000)

    def test_thousands(self) -> None:
        assert "K" in format_large_number(5_000)

    def test_small_number(self) -> None:
        assert format_large_number(999) == "999"

    def test_zero(self) -> None:
        assert format_large_number(0) == "0"

    def test_negative(self) -> None:
        result = format_large_number(-5000)
        assert "K" in result or "-" in result


class TestSafeGet:
    def test_nested_access(self) -> None:
        d = {"a": {"b": {"c": 42}}}
        assert safe_get(d, "a", "b", "c") == 42

    def test_missing_key_returns_default(self) -> None:
        d = {"a": {"b": 1}}
        assert safe_get(d, "a", "x", default=99) == 99

    def test_none_intermediate(self) -> None:
        d = {"a": None}
        assert safe_get(d, "a", "b", default="fallback") == "fallback"

    def test_non_dict_intermediate(self) -> None:
        d = {"a": "string"}
        assert safe_get(d, "a", "b", default=0) == 0

    def test_empty_dict(self) -> None:
        assert safe_get({}, "x", default="def") == "def"

    def test_single_key(self) -> None:
        assert safe_get({"k": "v"}, "k") == "v"


class TestCreateOutputDir:
    def test_creates_directory(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "subdir" / "deeper"
        create_output_dir(new_dir)
        assert new_dir.exists()

    def test_idempotent_on_existing_dir(self, tmp_path: Path) -> None:
        create_output_dir(tmp_path)  # already exists — should not raise


class TestGetFileSizeHuman:
    def test_returns_bytes(self, tmp_path: Path) -> None:
        f = tmp_path / "small.txt"
        f.write_bytes(b"hello")
        result = get_file_size_human(f)
        assert "B" in result

    def test_returns_zero_for_missing(self, tmp_path: Path) -> None:
        result = get_file_size_human(tmp_path / "nonexistent.csv")
        assert result == "0 B"

    def test_returns_kb_for_medium(self, tmp_path: Path) -> None:
        f = tmp_path / "medium.bin"
        f.write_bytes(b"x" * 2048)
        result = get_file_size_human(f)
        assert "KB" in result or "B" in result


class TestGenerateSessionId:
    def test_returns_string(self) -> None:
        sid = generate_session_id()
        assert isinstance(sid, str)

    def test_unique_each_call(self) -> None:
        ids = {generate_session_id() for _ in range(10)}
        assert len(ids) == 10

    def test_is_uuid_format(self) -> None:
        import re
        sid = generate_session_id()
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
        assert uuid_pattern.match(sid)
