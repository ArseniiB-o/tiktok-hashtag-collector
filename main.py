"""TikTok Hashtag Collector — CLI entry point (Section K)."""

from __future__ import annotations

import sys

# Z14: Python version check
if sys.version_info < (3, 11):
    sys.exit(
        f"Python 3.11+ required. You are running {sys.version_info.major}.{sys.version_info.minor}. "
        "Please upgrade Python and try again."
    )

import asyncio
import time
from pathlib import Path

import click

from src.config import AppConfig, ConfigValidationError, load_config
from src.dedup import DedupStore
from src.display import (
    _build_monitor_table,
    console,
    create_progress,
    show_banner,
    show_config_table,
    show_error,
    show_monitor_banner,
    show_stats_table,
    show_success,
    show_summary_table,
    show_warning,
)
from src.logger import get_logger, setup_logging
from src.models import ScraperStats
from src.storage import StorageManager
from src.utils import utcnow_naive

APP_VERSION: str = "1.0.0"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _bootstrap(verbose: bool, config_path: str | None) -> AppConfig:
    """Load config, set up logging, return AppConfig."""
    try:
        cfg_path = Path(config_path) if config_path else None
        config = load_config(cfg_path)
    except ConfigValidationError as exc:
        show_error(f"Configuration error: {exc}", hint="Check your config.yaml values")
        sys.exit(1)

    if verbose:
        config.log_level = "DEBUG"

    setup_logging(config)
    return config


async def _run_fetch(
    config: AppConfig,
    hashtag: str,
    limit: int,
    combined: bool,
) -> ScraperStats:
    """Core fetch pipeline: scrape → dedup → write."""
    from src.fallback_scraper import FallbackScraper
    from src.scraper import (
        HashtagNotFoundError,
        NetworkError,
        RateLimitError,
        ScraperInitializationError,
        TikTokScraper,
    )

    get_logger()
    dedup = DedupStore()
    storage = StorageManager(config, dedup)

    # Load existing IDs for deduplication
    existing_ids = storage.load_existing(hashtag, combined=combined)
    dedup.load(existing_ids)

    stats = ScraperStats(hashtag=hashtag, started_at=utcnow_naive())

    progress = create_progress(total=limit, description=f"#{hashtag}")

    async def _do_scrape(scraper_obj) -> None:
        nonlocal stats
        buffer: list = []

        with progress:
            task_id = (
                progress.task_ids[0]
                if progress.task_ids
                else progress.add_task(f"#{hashtag}", total=limit, rate=0.0)
            )
            start_ts = time.monotonic()

            async for record in scraper_obj.fetch_hashtag(hashtag, limit=limit):
                stats.total_fetched += 1

                if dedup.is_new(record.video_id):
                    buffer.append(record)
                    if len(buffer) >= config.write_batch_size:
                        written = storage.write_records(buffer, hashtag, combined=combined)
                        stats.new_records += written
                        buffer.clear()
                else:
                    stats.duplicates_skipped += 1

                elapsed = time.monotonic() - start_ts
                rate = stats.total_fetched / elapsed if elapsed > 0 else 0.0
                progress.update(task_id, advance=1, rate=rate)

        # Flush remaining buffer
        if buffer:
            written = storage.write_records(buffer, hashtag, combined=combined)
            stats.new_records += written
        storage.flush(hashtag, combined=combined)

    async def _run_fallback(reason: str) -> None:
        show_warning(f"Primary scraper failed ({reason}); switching to fallback HTTP scraper...")
        fallback = FallbackScraper(config)
        fallback.initialize()
        try:
            await _do_scrape(fallback)
        finally:
            fallback.close()

    # Try primary scraper; fall back on init, network, or rate-limit failure
    try:
        async with TikTokScraper(config) as scraper:
            await _do_scrape(scraper)
    except ScraperInitializationError as e:
        stats.errors += 1
        try:
            await _run_fallback(str(e))
        except (NetworkError, RateLimitError, HashtagNotFoundError) as fe:
            show_error(f"Fallback scraper also failed: {fe}")
            stats.errors += 1
    except (NetworkError, RateLimitError) as e:
        stats.errors += 1
        try:
            await _run_fallback(str(e))
        except (NetworkError, RateLimitError) as fe:
            show_error(
                f"Both scrapers failed: {fe}",
                hint="Set TIKTOK_SESSION_ID in .env, or configure a proxy in config.yaml",
            )
            stats.errors += 1
        except HashtagNotFoundError as fe:
            show_error(str(fe), hint=f"Check that #{hashtag} has public videos")
            stats.errors += 1
    except HashtagNotFoundError as e:
        show_error(str(e), hint=f"Check that #{hashtag} has public videos")
        stats.errors += 1

    stats.finished_at = utcnow_naive()
    return stats


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """TikTok Hashtag Collector — collect video metadata by hashtag."""


@cli.command("fetch")
@click.argument("hashtags", nargs=-1, required=True)
@click.option("--limit", default=500, show_default=True, help="Max videos per hashtag")
@click.option("--format", "fmt", default=None, help="Output format: csv|excel|both")
@click.option("--output-dir", "output_dir", default=None, help="Output directory")
@click.option("--combined", is_flag=True, default=False, help="Merge all hashtags into one file")
@click.option("--no-progress", is_flag=True, default=False, help="Disable progress bar")
@click.option("--verbose", is_flag=True, default=False, help="Enable debug logging")
@click.option("--config", "config_path", default=None, help="Path to config.yaml")
def cmd_fetch(
    hashtags: tuple[str, ...],
    limit: int,
    fmt: str | None,
    output_dir: str | None,
    combined: bool,
    no_progress: bool,
    verbose: bool,
    config_path: str | None,
) -> None:
    """K2 — Fetch videos for one or more HASHTAGS and save to CSV/Excel."""
    config = _bootstrap(verbose, config_path)
    show_banner(APP_VERSION)

    if fmt:
        config.output_format = fmt
    if output_dir:
        config.output_dir = Path(output_dir)

    all_stats = []
    total_errors = 0

    for hashtag in hashtags:
        clean = hashtag.lstrip("#")
        click.echo(f"\nFetching hashtag: #{clean}  (limit: {limit})")

        stats = asyncio.run(_run_fetch(config, clean, limit, combined))
        total_errors += stats.errors
        all_stats.append(
            {
                "hashtag": clean,
                "output_path": str(config.output_dir),
                "total_fetched": stats.total_fetched,
                "new_records": stats.new_records,
                "duplicates_skipped": stats.duplicates_skipped,
                "duration_seconds": (
                    (stats.finished_at - stats.started_at).total_seconds()
                    if stats.finished_at
                    else 0
                ),
            }
        )

    show_summary_table(all_stats)
    sys.exit(0 if total_errors == 0 else 1)


@cli.command("watch")
@click.argument("hashtags", nargs=-1, required=True)
@click.option("--interval", default=15, show_default=True, help="Check interval in minutes")
@click.option("--limit", default=50, show_default=True, help="Max new videos per check")
@click.option("--format", "fmt", default=None, help="Output format: csv|excel|both")
@click.option("--config", "config_path", default=None, help="Path to config.yaml")
def cmd_watch(
    hashtags: tuple[str, ...],
    interval: int,
    limit: int,
    fmt: str | None,
    config_path: str | None,
) -> None:
    """K3 — Continuously monitor HASHTAGS for new videos."""
    config = _bootstrap(False, config_path)
    show_monitor_banner(list(hashtags))

    if fmt:
        config.output_format = fmt

    # One shared dedup + storage for all hashtags
    dedup = DedupStore()
    storage = StorageManager(config, dedup)

    # Pre-load existing IDs
    for hashtag in hashtags:
        clean = hashtag.lstrip("#")
        existing = storage.load_existing(clean)
        dedup.load(existing)

    from src.scheduler import MonitorScheduler

    scheduler = MonitorScheduler(config, storage)

    for hashtag in hashtags:
        clean = hashtag.lstrip("#")
        scheduler.add_hashtag(clean, interval_minutes=interval, limit_per_run=limit)

    scheduler.start()

    # K3: Live table refreshing every 5 seconds (single Live instance, updated in-place)
    from rich.live import Live

    try:
        with Live(
            _build_monitor_table(scheduler.get_job_status()),
            console=console,
            refresh_per_second=4,
        ) as live:
            while True:
                time.sleep(5)
                live.update(_build_monitor_table(scheduler.get_job_status()))
    except (KeyboardInterrupt, SystemExit):
        scheduler.stop()


@cli.command("stats")
@click.option(
    "--output-dir", "output_dir", default="output", show_default=True, help="Output directory"
)
def cmd_stats(output_dir: str) -> None:
    """K4 — Show statistics for existing output files."""
    import pandas as pd

    from src.utils import get_file_size_human

    output_path = Path(output_dir)
    if not output_path.exists():
        show_warning(f"Output directory '{output_dir}' does not exist")
        return

    csv_files = list(output_path.glob("*.csv"))
    if not csv_files:
        show_warning(f"No CSV files found in '{output_dir}'")
        return

    file_stats = []
    for csv_file in sorted(csv_files):
        try:
            df = pd.read_csv(csv_file, dtype=str)
            record_count = len(df)
            unique_authors = (
                df["author_username"].nunique() if "author_username" in df.columns else 0
            )
            earliest = df["created_at"].min() if "created_at" in df.columns else ""
            latest = df["created_at"].max() if "created_at" in df.columns else ""
            # Extract hashtag from filename (e.g. "cats_2024-01-15.csv" → "cats")
            parts = csv_file.stem.rsplit("_", 1)
            hashtag = parts[0] if len(parts) == 2 else csv_file.stem
            date = parts[1] if len(parts) == 2 else ""
        except (pd.errors.ParserError, pd.errors.EmptyDataError, OSError) as exc:
            show_warning(f"Unable to read {csv_file.name}: {exc}")
            record_count, unique_authors, earliest, latest = 0, 0, "", ""
            hashtag, date = csv_file.stem, ""

        file_stats.append(
            {
                "filename": csv_file.name,
                "hashtag": hashtag,
                "date": date,
                "record_count": record_count,
                "file_size": get_file_size_human(csv_file),
                "unique_authors": unique_authors,
                "earliest_date": str(earliest)[:10],
                "latest_date": str(latest)[:10],
            }
        )

    show_stats_table(file_stats)


@cli.command("clean")
@click.option("--output-dir", "output_dir", default="output", show_default=True)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be removed without modifying files",
)
def cmd_clean(output_dir: str, dry_run: bool) -> None:
    """K5 — Remove duplicate entries from existing output files."""
    import pandas as pd

    output_path = Path(output_dir)
    csv_files = list(output_path.glob("*.csv"))

    if not csv_files:
        show_warning(f"No CSV files found in '{output_dir}'")
        return

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, dtype=str)
            original_len = len(df)

            if "video_id" not in df.columns:
                show_warning(f"Skipping {csv_file.name}: no video_id column")
                continue

            df_clean = df.drop_duplicates(subset=["video_id"], keep="first")
            removed = original_len - len(df_clean)

            if removed == 0:
                show_success(f"{csv_file.name}: no duplicates found")
                continue

            if dry_run:
                show_warning(f"{csv_file.name}: would remove {removed} duplicate rows (dry run)")
            else:
                backup_path = csv_file.with_suffix(csv_file.suffix + ".bak")
                backup_path.write_bytes(csv_file.read_bytes())
                df_clean.to_csv(csv_file, index=False, encoding="utf-8-sig")
                show_success(
                    f"{csv_file.name}: removed {removed} duplicate rows "
                    f"(backup → {backup_path.name})"
                )

        except (pd.errors.ParserError, pd.errors.EmptyDataError, OSError) as e:
            show_error(f"Error processing {csv_file.name}: {e}")


@cli.command("config")
@click.option("--show", is_flag=True, default=False, help="Show current merged config")
@click.option("--validate", is_flag=True, default=False, help="Validate config and report issues")
@click.option("--config", "config_path", default=None)
def cmd_config(show: bool, validate: bool, config_path: str | None) -> None:
    """K6 — Show or validate current configuration."""
    try:
        cfg_path = Path(config_path) if config_path else None
        config = load_config(cfg_path)
    except ConfigValidationError as exc:
        show_error(f"Config invalid: {exc}")
        sys.exit(1)

    if show or not validate:
        import dataclasses

        config_dict = {
            k: str(v)
            for k, v in dataclasses.asdict(config).items()
            if k not in ("tiktok_session_id", "tiktok_verify_fp", "proxy_password")
        }
        show_config_table(config_dict)

    if validate:
        show_success("Configuration is valid")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
