"""display.py — All terminal output for tiktok-hashtag-collector.

Other modules must NEVER use print() directly — import from this module.
"""

from __future__ import annotations

import sys

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

# Force UTF-8 stdout so Rich emojis/symbols render on Windows cp125x locales.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

# Single shared console instance used by all output functions.
# legacy_windows=False prevents the legacy cp125x renderer that chokes on ✓, ⚠, ●.
console = Console(legacy_windows=False)


# ---------------------------------------------------------------------------
# Banner helpers
# ---------------------------------------------------------------------------


def show_banner(version: str) -> None:
    """Print the application startup banner with version info."""
    content = f"[bold cyan]TikTok Hashtag Collector[/bold cyan]  [dim]v{version}[/dim]"
    console.print(
        Panel(content, box=box.DOUBLE, border_style="cyan", expand=False)
    )


def show_monitor_banner(hashtags: list[str]) -> None:
    """Print the monitor-mode banner showing the number of watched hashtags."""
    n = len(hashtags)
    tag_list = "  ".join(f"[bold]#{h}[/bold]" for h in hashtags[:5])
    extra = f"  [dim]…+{n - 5} more[/dim]" if n > 5 else ""
    content = (
        f"[bold cyan]TikTok Hashtag Collector[/bold cyan]  "
        f"[yellow]Monitor Mode — watching {n} hashtag{'s' if n != 1 else ''}[/yellow]\n"
        f"{tag_list}{extra}"
    )
    console.print(
        Panel(content, box=box.DOUBLE, border_style="yellow", expand=False)
    )


# ---------------------------------------------------------------------------
# Status messages
# ---------------------------------------------------------------------------


def show_error(
    message: str,
    hint: str = "",
    log_file: str = "logs/scraper.log",
) -> None:
    """Print a red bordered error panel with an optional fix hint."""
    lines: list[str] = [message]
    if hint:
        lines.append(f"\n[bold]Suggested fix:[/bold] {hint}")
    lines.append(f"[dim]See {log_file} for details[/dim]")
    body = "\n".join(lines)
    console.print(
        Panel(body, title="[bold red]Error[/bold red]", border_style="red", expand=False)
    )


def show_success(message: str) -> None:
    """Print a green success message with a checkmark."""
    console.print(f"[bold green]✓[/bold green] {message}")


def show_warning(message: str) -> None:
    """Print a yellow warning message."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------


def create_progress(total: int, description: str) -> Progress:
    """Create and return a configured Rich Progress instance.

    The caller should use the returned object as a context manager and create
    tasks on it as needed.  A default task is added automatically.

    Args:
        total:       Total number of items to process.
        description: Label shown next to the spinner.

    Returns:
        A :class:`rich.progress.Progress` instance with a task already added.
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TextColumn("•"),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("• {task.fields[rate]:.1f} rec/s"),
        transient=False,
        console=console,
    )
    progress.add_task(description, total=total, rate=0.0)
    return progress


# ---------------------------------------------------------------------------
# Summary / stats tables
# ---------------------------------------------------------------------------


def _format_duration(seconds: float) -> str:
    """Return a human-readable duration string."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, rem = divmod(s, 60)
    return f"{m}m {rem}s"


def show_summary_table(stats_list: list[dict]) -> None:
    """Render a per-hashtag run summary table.

    Each dict in *stats_list* must contain:
        hashtag, output_path, total_fetched, new_records,
        duplicates_skipped, duration_seconds
    """
    table = Table(
        title="[bold]Run Summary[/bold]",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("Hashtag", style="cyan", no_wrap=True)
    table.add_column("Output File", style="dim")
    table.add_column("Fetched", justify="right")
    table.add_column("New", justify="right", style="green")
    table.add_column("Duplicates", justify="right", style="yellow")
    table.add_column("Duration", justify="right")

    for row in stats_list:
        table.add_row(
            f"#{row['hashtag']}",
            str(row["output_path"]),
            str(row["total_fetched"]),
            str(row["new_records"]),
            str(row["duplicates_skipped"]),
            _format_duration(row["duration_seconds"]),
        )

    console.print(table)


def show_stats_table(file_stats: list[dict]) -> None:
    """Render a file-level statistics table for the `stats` CLI command.

    Each dict in *file_stats* must contain:
        filename, hashtag, date, record_count, file_size,
        unique_authors, earliest_date, latest_date
    """
    table = Table(
        title="[bold]File Statistics[/bold]",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("Filename", style="dim", no_wrap=True)
    table.add_column("Hashtag", style="cyan")
    table.add_column("Date")
    table.add_column("Records", justify="right")
    table.add_column("File Size", justify="right")
    table.add_column("Unique Authors", justify="right")
    table.add_column("Earliest")
    table.add_column("Latest")

    for row in file_stats:
        table.add_row(
            str(row["filename"]),
            f"#{row['hashtag']}",
            str(row["date"]),
            str(row["record_count"]),
            str(row["file_size"]),
            str(row["unique_authors"]),
            str(row["earliest_date"]),
            str(row["latest_date"]),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Live monitor
# ---------------------------------------------------------------------------


def _build_monitor_table(jobs: list[dict]) -> Table:
    """Build the monitor table from the current job snapshot."""
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        header_style="bold blue",
        expand=True,
    )
    table.add_column("Hashtag", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Last Check")
    table.add_column("Next Check")
    table.add_column("Records", justify="right")
    table.add_column("Last Run New", justify="right")

    _status_styles: dict[str, str] = {
        "active": "[bold green]● Active[/bold green]",
        "paused": "[bold yellow]● Paused[/bold yellow]",
        "error": "[bold red]✗ Error[/bold red]",
    }

    for job in jobs:
        raw_status = str(job.get("status", "")).lower()
        status_cell = _status_styles.get(raw_status, str(job.get("status", "")))
        table.add_row(
            f"#{job['hashtag']}",
            status_cell,
            str(job.get("last_run", "—")),
            str(job.get("next_run", "—")),
            str(job.get("total_records_this_session", 0)),
            str(job.get("last_run_new_records", 0)),
        )

    return table


def show_live_monitor_table(jobs: list[dict]) -> Live:
    """Return a Rich Live context manager wrapping a live monitor table.

    Usage::

        with show_live_monitor_table(jobs) as live:
            # update the table by calling live.update(new_table)
            ...

    Args:
        jobs: List of job status dicts.  See module docstring for keys.

    Returns:
        A :class:`rich.live.Live` instance ready to be used as a context manager.
    """
    table = _build_monitor_table(jobs)
    return Live(table, console=console, refresh_per_second=4)


# ---------------------------------------------------------------------------
# Config table
# ---------------------------------------------------------------------------


def show_config_table(config_dict: dict) -> None:
    """Render a two-column Setting / Value table for the current config."""
    table = Table(
        title="[bold]Configuration[/bold]",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("Setting", style="bold cyan", no_wrap=True)
    table.add_column("Value")

    for key, value in config_dict.items():
        table.add_row(str(key), str(value))

    console.print(table)
