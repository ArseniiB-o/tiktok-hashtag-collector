"""APScheduler-based monitoring scheduler for continuous hashtag watching (Section I)."""

from __future__ import annotations

import asyncio
import signal
import threading
import uuid
from typing import Any

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import AppConfig
from src.display import show_success
from src.logger import get_logger
from src.models import MonitorJobStatus
from src.storage import StorageManager
from src.utils import utcnow_naive

# I5: Interval constraints
MIN_INTERVAL_MINUTES: int = 5
MAX_INTERVAL_MINUTES: int = 1440
DEFAULT_INTERVAL_MINUTES: int = 15
MAX_WORKERS: int = 4


class MonitorScheduler:
    """Manages periodic scraping jobs for auto-monitor mode.

    Uses APScheduler BackgroundScheduler with one job per hashtag.
    Handles graceful shutdown on SIGINT/SIGTERM.
    """

    def __init__(self, config: AppConfig, storage: StorageManager) -> None:
        """Initialize scheduler with application config and storage manager."""
        self._config = config
        self._storage = storage
        self._logger = get_logger()
        self._job_statuses: dict[str, MonitorJobStatus] = {}

        self._scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": ThreadPoolExecutor(max_workers=MAX_WORKERS)},
            job_defaults={"coalesce": True, "max_instances": 1},
        )

        # I8: Register signal handlers for graceful shutdown.
        # Python only allows signal registration from the main thread; skip silently otherwise.
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, self._handle_shutdown_signal)
                signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
            except (ValueError, OSError) as exc:
                self._logger.debug(f"Signal handlers not registered: {exc}")

    def _handle_shutdown_signal(self, signum: int, frame: Any) -> None:
        """Handle SIGINT/SIGTERM by stopping the scheduler cleanly."""
        self._logger.info(f"Received signal {signum}, shutting down...")
        self.stop()

    def add_hashtag(
        self,
        hashtag: str,
        interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
        limit_per_run: int = 50,
    ) -> str:
        """Register a hashtag for periodic monitoring.

        Args:
            hashtag: Hashtag to monitor (with or without #).
            interval_minutes: How often to check for new videos.
            limit_per_run: Max videos to fetch per run.

        Returns:
            Job ID (UUID string) for later reference.
        """
        # Clamp interval to valid range
        interval_minutes = max(MIN_INTERVAL_MINUTES, min(interval_minutes, MAX_INTERVAL_MINUTES))

        clean_tag = hashtag.lstrip("#").lower()
        job_id = str(uuid.uuid4())

        status = MonitorJobStatus(
            hashtag=clean_tag,
            job_id=job_id,
            interval_minutes=interval_minutes,
        )
        self._job_statuses[job_id] = status

        self._scheduler.add_job(
            func=self._run_scrape_job,
            trigger="interval",
            minutes=interval_minutes,
            id=job_id,
            args=[job_id, clean_tag, limit_per_run],
            next_run_time=utcnow_naive(),  # I6: Run immediately on start
        )

        self._logger.info(
            f"Added monitor job for #{clean_tag} every {interval_minutes}m (id={job_id})"
        )
        return job_id

    def _run_scrape_job(self, job_id: str, hashtag: str, limit: int) -> None:
        """Execute a single scraping run for a monitored hashtag.

        Bridges sync APScheduler → async scraper via asyncio.run().
        """
        status = self._job_statuses.get(job_id)
        if status:
            status.is_running = True
            status.last_run = utcnow_naive()
            # Update next run time
            apscheduler_job = self._scheduler.get_job(job_id)
            if apscheduler_job and apscheduler_job.next_run_time:
                status.next_run = apscheduler_job.next_run_time.replace(tzinfo=None)

        new_count = 0
        error_msg: str | None = None

        try:
            # I4: Create fresh event loop for this thread
            new_count = asyncio.run(self._async_scrape(hashtag, limit))
        except Exception as e:
            error_msg = str(e)
            self._logger.error(f"Error in monitor job for #{hashtag}: {e}")
            if status:
                status.last_run_error = error_msg
        finally:
            if status:
                status.is_running = False
                status.last_run_new_records = new_count
                status.total_records_this_session += new_count

        self._logger.info(
            f"Monitor run for #{hashtag}: +{new_count} new records",
            extra={"hashtag": hashtag, "count": new_count},
        )

    async def _async_scrape(self, hashtag: str, limit: int) -> int:
        """Run async scraping pipeline and write results to storage.

        Returns:
            Number of new records written.
        """
        from src.fallback_scraper import FallbackScraper
        from src.scraper import ScraperInitializationError, TikTokScraper

        async def _drain(src: Any) -> int:
            # No pre-filter via dedup.is_new(): that introduced a TOCTOU race
            # under APScheduler's ThreadPoolExecutor. write_records() performs
            # an atomic filter+mark under the storage write lock, so duplicate
            # detection happens exactly once and exactly correctly.
            buffer: list = []
            async for record in src.fetch_hashtag(hashtag, limit=limit):
                buffer.append(record)
            written = self._storage.write_records(buffer, hashtag)
            self._storage.flush(hashtag)
            return written

        try:
            async with TikTokScraper(self._config) as scraper:
                return await _drain(scraper)
        except ScraperInitializationError as e:
            self._logger.warning(f"TikTokApi failed, trying fallback: {e}")
            fallback = FallbackScraper(self._config)
            fallback.initialize()
            try:
                return await _drain(fallback)
            finally:
                fallback.close()

    def start(self) -> None:
        """Start the background scheduler."""
        self._scheduler.start()
        self._logger.info("MonitorScheduler started")

        # Log next run times
        for job_id, status in self._job_statuses.items():
            apscheduler_job = self._scheduler.get_job(job_id)
            if apscheduler_job:
                show_success(f"Watching #{status.hashtag} every {status.interval_minutes}m")

    def stop(self) -> None:
        """I7: Graceful shutdown — wait for running jobs, flush storage."""
        self._logger.info("Stopping MonitorScheduler...")
        try:
            self._scheduler.shutdown(wait=True)
        except Exception as e:
            self._logger.debug(f"Scheduler shutdown error: {e}")

        # Flush any buffered records for all watched hashtags
        for status in self._job_statuses.values():
            try:
                self._storage.flush(status.hashtag)
            except Exception as e:
                self._logger.debug(f"Flush error for #{status.hashtag}: {e}")

        total = sum(s.total_records_this_session for s in self._job_statuses.values())
        show_success(f"Monitor stopped. Total new records this session: {total}")

    def get_job_status(self) -> list[dict]:
        """Return current status for all monitored hashtags."""
        result = []
        for job_id, status in self._job_statuses.items():
            apscheduler_job = self._scheduler.get_job(job_id)
            next_run = None
            if apscheduler_job and apscheduler_job.next_run_time:
                next_run = apscheduler_job.next_run_time.replace(tzinfo=None).isoformat()

            result.append(
                {
                    "hashtag": status.hashtag,
                    "job_id": job_id,
                    "status": "running" if status.is_running else "active",
                    "last_run": status.last_run.isoformat() if status.last_run else None,
                    "next_run": next_run,
                    "total_records_this_session": status.total_records_this_session,
                    "last_run_new_records": status.last_run_new_records,
                    "last_run_error": status.last_run_error,
                }
            )
        return result
