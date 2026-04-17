"""Fallback HTTP scraper using curl_cffi for TLS fingerprint spoofing.

Activated automatically when TikTokApi fails (Section F).
Implements the same fetch_hashtag interface as TikTokScraper.
"""
from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from typing import Any

from src.config import AppConfig
from src.logger import get_logger
from src.models import VideoRecord
from src.scraper import (
    HashtagNotFoundError,
    NetworkError,
    RateLimitError,
    ScraperInitializationError,
)
from src.utils import normalize_hashtag

# F4: Required headers mimicking a real Chrome browser
_BASE_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.tiktok.com/",
    "Origin": "https://www.tiktok.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

_TIKTOK_WEB_ID: str = "1988"  # TikTok web app ID
_PAGE_SIZE: int = 30  # TikTok's default API page size
_CHALLENGE_DETAIL_URL: str = "https://www.tiktok.com/api/challenge/detail/"
_CHALLENGE_ITEMS_URL: str = "https://www.tiktok.com/api/challenge/item_list/"


class FallbackScraper:
    """HTTP-based TikTok scraper using curl_cffi Chrome120 TLS fingerprinting.

    Used as fallback when TikTokApi (Playwright-based) fails.
    Implements the same async-generator interface as TikTokScraper.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize with application config."""
        self._config = config
        self._logger = get_logger()
        self._session: Any = None
        self._initialized: bool = False

    def initialize(self) -> None:
        """Create a curl_cffi session impersonating Chrome 120."""
        try:
            from curl_cffi import requests as cffi_requests  # type: ignore[import]

            self._session = cffi_requests.Session(impersonate="chrome120")
            self._initialized = True
            self._logger.info("FallbackScraper initialized with curl_cffi Chrome120")
        except ImportError as e:
            raise ScraperInitializationError(
                f"curl_cffi not installed. Run: pip install curl-cffi. Details: {e}"
            ) from e
        except Exception as e:
            raise ScraperInitializationError(f"Failed to initialize FallbackScraper: {e}") from e

    def _get_headers(self) -> dict[str, str]:
        """Build request headers with a random user agent."""
        from src.scraper import USER_AGENTS

        ua = random.choice(USER_AGENTS)
        return {**_BASE_HEADERS, "User-Agent": ua}

    def _resolve_challenge_id(self, hashtag: str) -> str:
        """Resolve a hashtag name to its TikTok challengeID.

        Args:
            hashtag: Normalized hashtag name (no #).

        Returns:
            The challengeID string.

        Raises:
            HashtagNotFoundError: If the hashtag doesn't exist.
            NetworkError: On HTTP errors.
        """
        if self._session is None:
            raise ScraperInitializationError("Call initialize() first")

        params = {"challengeName": hashtag}
        try:
            response = self._session.get(
                _CHALLENGE_DETAIL_URL,
                headers=self._get_headers(),
                params=params,
                timeout=15,
            )
        except Exception as e:
            raise NetworkError(f"Failed to resolve challengeID for #{hashtag}: {e}") from e

        if response.status_code == 404:
            raise HashtagNotFoundError(f"Hashtag #{hashtag} not found")
        if response.status_code == 429:
            raise RateLimitError(f"Rate limited while resolving #{hashtag}")
        if response.status_code != 200:
            raise NetworkError(f"HTTP {response.status_code} for #{hashtag}")

        try:
            data: dict = response.json()
        except Exception as e:
            raise NetworkError(f"Invalid JSON response for #{hashtag}: {e}") from e

        challenge_info = data.get("challengeInfo") or {}
        challenge = challenge_info.get("challenge") or {}
        challenge_id: str = str(challenge.get("id") or "")
        if not challenge_id:
            raise HashtagNotFoundError(f"Could not extract challengeID for #{hashtag}")

        return challenge_id

    def _fetch_page(self, challenge_id: str, cursor: int) -> tuple[list[dict], int, bool]:
        """Fetch one page of videos for a challengeID.

        Returns:
            Tuple of (videos_list, next_cursor, has_more).
        """
        if self._session is None:
            raise ScraperInitializationError("Call initialize() first")

        params = {
            "challengeID": challenge_id,
            "count": str(_PAGE_SIZE),
            "cursor": str(cursor),
            "aid": _TIKTOK_WEB_ID,
            "app_language": "en",
            "device_platform": "web_pc",
        }
        try:
            response = self._session.get(
                _CHALLENGE_ITEMS_URL,
                headers=self._get_headers(),
                params=params,
                timeout=20,
            )
        except Exception as e:
            raise NetworkError(f"Failed to fetch page (cursor={cursor}): {e}") from e

        if response.status_code == 429:
            raise RateLimitError("Rate limited on item_list endpoint")
        if response.status_code != 200:
            raise NetworkError(f"HTTP {response.status_code} on item_list")

        try:
            data: dict = response.json()
        except Exception as e:
            raise NetworkError(f"Invalid JSON on item_list: {e}") from e

        videos: list[dict] = data.get("itemList") or []
        try:
            next_cursor: int = int(data.get("cursor") or 0)
        except (ValueError, TypeError):
            next_cursor = 0
        has_more: bool = bool(data.get("hasMore", False))

        return videos, next_cursor, has_more

    async def fetch_hashtag(
        self, hashtag: str, limit: int = 500
    ) -> AsyncIterator[VideoRecord]:  # type: ignore[override]
        """Async generator yielding VideoRecord objects for videos under the given hashtag.

        Same interface as TikTokScraper.fetch_hashtag.

        Args:
            hashtag: Hashtag to search.
            limit: Maximum number of videos to return.

        Yields:
            VideoRecord for each video found.
        """
        if not self._initialized:
            raise ScraperInitializationError("Call initialize() first")

        clean_hashtag = normalize_hashtag(hashtag)

        # F2: Resolve challengeID first
        challenge_id = self._resolve_challenge_id(clean_hashtag)
        self._logger.info(f"Resolved #{clean_hashtag} → challengeID={challenge_id}")

        count = 0
        cursor = 0

        while count < limit:
            # Run synchronous HTTP call in executor to keep async-friendly
            loop = asyncio.get_running_loop()
            try:
                videos, cursor, has_more = await loop.run_in_executor(
                    None, self._fetch_page, challenge_id, cursor
                )
            except RateLimitError:
                raise
            except (HashtagNotFoundError, NetworkError):
                raise

            for raw in videos:
                if count >= limit:
                    return
                record = VideoRecord.from_tiktok_response(raw, clean_hashtag)
                yield record
                count += 1

                # E8-B: Anti-bot delay
                await asyncio.sleep(
                    random.uniform(
                        self._config.min_delay_seconds, self._config.max_delay_seconds
                    )
                )

            if not has_more or not videos:
                break

        self._logger.info(f"FallbackScraper: fetched {count} videos for #{clean_hashtag}")

    def close(self) -> None:
        """Close the curl_cffi session."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception as e:
                self._logger.debug(f"Error closing fallback session: {e}")
        self._initialized = False
        self._session = None
