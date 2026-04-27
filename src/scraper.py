"""TikTok scraper module using TikTokApi (unofficial)."""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from typing import Any

from src.config import AppConfig
from src.logger import get_logger
from src.models import VideoRecord
from src.utils import normalize_hashtag

# E8-A: Realistic Chrome/Safari user agent strings for rotation
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
]

LOG_INTERVAL: int = 50  # Log progress every N records


# --- E9: Custom exception hierarchy ---


class ScraperError(Exception):
    """Base exception for scraper errors."""


class ScraperInitializationError(ScraperError):
    """Raised when TikTokApi cannot be initialized."""


class HashtagNotFoundError(ScraperError):
    """Raised when a hashtag has no videos or doesn't exist."""


class RateLimitError(ScraperError):
    """Raised when TikTok rate-limits the scraper."""


class AuthenticationError(ScraperError):
    """Raised when TikTok session authentication fails."""


class NetworkError(ScraperError):
    """Raised on unrecoverable network errors."""


# --- E2: Main scraper class ---


class TikTokScraper:
    """Scrapes TikTok video metadata for given hashtags using TikTokApi."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize with application config. Does NOT start Playwright yet."""
        self._config = config
        self._api: Any = None
        self._initialized: bool = False
        self._logger = get_logger()
        self._user_agents: list[str] = USER_AGENTS

    async def initialize(self) -> None:
        """Start Playwright and initialize TikTokApi. Must be called before fetch_hashtag."""
        try:
            from TikTokApi import TikTokApi  # type: ignore[import]

            kwargs: dict = {}
            if self._config.tiktok_verify_fp:
                kwargs["custom_verify_fp"] = self._config.tiktok_verify_fp

            self._api = TikTokApi(**kwargs)

            session_kwargs: dict[str, Any] = {
                "ms_tokens": (
                    [self._config.tiktok_session_id] if self._config.tiktok_session_id else []
                ),
                "num_sessions": 1,
                "sleep_after": 3,
                "headless": self._config.headless,
            }
            # Forward the user-configured proxy into Playwright so primary
            # scraper traffic is actually anonymised. Earlier versions silently
            # ignored proxy_url, exposing the user's real IP to TikTok.
            if self._config.proxy_url:
                session_kwargs["proxies"] = [self._config.proxy_url]
            await self._api.create_sessions(**session_kwargs)
            self._initialized = True
            self._logger.info("TikTokApi initialized successfully")
        except ImportError as e:
            raise ScraperInitializationError(
                f"TikTokApi not installed. Run: pip install TikTokApi. Details: {e}"
            ) from e
        except Exception as e:
            raise ScraperInitializationError(f"Failed to initialize TikTok API: {e}") from e

    async def fetch_hashtag(
        self, hashtag: str, limit: int = 500
    ) -> AsyncIterator[VideoRecord]:  # type: ignore[override]
        """Async generator yielding VideoRecord objects for videos under the given hashtag.

        Args:
            hashtag: Hashtag to search (with or without leading #).
            limit: Maximum number of videos to fetch.

        Yields:
            VideoRecord for each video found.

        Raises:
            ScraperInitializationError: If initialize() was not called.
            RateLimitError: If TikTok rate-limits the scraper after max retries.
            HashtagNotFoundError: If the hashtag has no videos.
            NetworkError: On unrecoverable network failures.
        """
        if not self._initialized or self._api is None:
            raise ScraperInitializationError(
                "Call initialize() (or use as async context manager) first"
            )

        clean_hashtag = normalize_hashtag(hashtag)
        count = 0

        try:
            tag = self._api.hashtag(name=clean_hashtag)
            async for video in tag.videos(count=limit):
                raw: dict = video.as_dict if hasattr(video, "as_dict") else {}
                record = VideoRecord.from_tiktok_response(raw, clean_hashtag)

                # E8-B: Random delay between records to simulate human browsing
                delay = random.uniform(
                    self._config.min_delay_seconds, self._config.max_delay_seconds
                )  # nosec B311 — intentional jitter, not crypto
                await asyncio.sleep(delay)

                yield record
                count += 1

                if count % LOG_INTERVAL == 0:
                    self._logger.debug(
                        f"Fetched {count} videos for #{clean_hashtag}",
                        extra={"hashtag": clean_hashtag, "count": count},
                    )

        except (GeneratorExit, asyncio.CancelledError):
            self._logger.info(f"Fetch cancelled for #{clean_hashtag} after {count} videos")
            return
        except Exception as e:
            err_str = str(e).lower()
            if "rate" in err_str or "429" in err_str or "too many" in err_str:
                raise RateLimitError(str(e)) from e
            if "not found" in err_str or "no results" in err_str:
                raise HashtagNotFoundError(f"Hashtag #{clean_hashtag} not found: {e}") from e
            self._logger.warning(f"Network error fetching #{clean_hashtag}: {e}")
            raise NetworkError(str(e)) from e

    async def close(self) -> None:
        """Shut down Playwright and TikTokApi cleanly."""
        if self._api is not None:
            try:
                await self._api.close_sessions()
            except Exception as e:
                self._logger.debug(f"Error closing TikTokApi sessions: {e}")
        self._initialized = False
        self._api = None

    # E10: Async context manager support

    async def __aenter__(self) -> TikTokScraper:
        """Initialize on entry."""
        await self.initialize()
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close on exit."""
        await self.close()
