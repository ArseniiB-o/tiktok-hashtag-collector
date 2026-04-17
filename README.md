# TikTok Hashtag Collector

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/tests-77%20passing-brightgreen.svg)](./tests)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A zero-cloud, locally-running Python CLI that harvests TikTok video metadata by
hashtag and streams results to **CSV / Excel** with dedup, date rotation, live
monitoring, anti-bot measures, and a Rich-powered terminal UI.

Designed for researchers, trend analysts, and marketers who want a
**reproducible, scriptable dataset** of TikTok videos without paying for a
SaaS dashboard.

---

## Features

- **Two collection modes** — one-shot `fetch` or continuous `watch` with APScheduler
- **Dual scraper backends** — primary `TikTokApi` (Playwright) with automatic
  fallback to a `curl_cffi` HTTP scraper spoofing Chrome120 TLS fingerprints
- **23 metadata fields per video** — IDs, URLs, author stats, engagement
  counters (likes / comments / shares / views / bookmarks), music info,
  challenges/hashtags, language, region, timestamps
- **Smart output** — CSV with UTF-8 BOM (Excel-friendly) + optional `.xlsx`
  with bold headers, frozen panes, auto-width columns, and clickable URL
  hyperlinks
- **Deduplication** — thread-safe in-memory set; pre-loads existing
  `video_id`s at startup so re-runs never duplicate rows
- **Daily file rotation** — `cats_2026-04-17.csv` → new file on the next day
- **Monitor mode** — per-hashtag background jobs, live Rich status table,
  graceful `SIGINT`/`SIGTERM` shutdown with buffer flushing
- **Anti-bot** — 10 rotating User-Agents, randomised per-video delays,
  exponential back-off on rate limits, optional HTTP / HTTPS / SOCKS5 proxy
- **Layered config** — `AppConfig` defaults → `config.yaml` → `.env` → env
  vars → CLI flags (highest wins)
- **Structured logging** — JSON Lines rotating file handler (10 MB × 5) +
  Rich console for warnings
- **Cross-platform** — fully tested on Windows (including non-UTF-8 locales),
  macOS, and Linux

---

## Requirements

- **Python 3.11+**
- **pip** and **venv**
- **~500 MB disk** for Playwright's bundled Chromium
- Optional: proxy subscription, TikTok login cookies for higher rate limits

---

## Installation

```bash
git clone https://github.com/<your-user>/tiktok-hashtag-collector.git
cd tiktok-hashtag-collector

# macOS / Linux
bash setup.sh

# Windows (cmd or PowerShell)
setup.bat
```

The setup script creates a `.venv`, installs dependencies, downloads
Chromium for Playwright, copies `.env.example` → `.env`, and creates
`output/` and `logs/` directories.

### Manual install

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env               # Windows: copy .env.example .env
```

---

## Quick start

```bash
# 1. (Optional but recommended) add TikTok session cookies to .env
#    — see "Getting a TikTok session" below
$ cat .env
TIKTOK_SESSION_ID=<your ms_token>
TIKTOK_VERIFY_FP=<your verifyFp>

# 2. One-shot fetch: up to 200 videos for #cats
$ python main.py fetch cats --limit 200

# 3. Continuous monitor: watch #cats and #dogs every 10 min
$ python main.py watch cats dogs --interval 10

# 4. Inspect collected data
$ python main.py stats

# 5. Deduplicate existing CSVs (creates .bak backup)
$ python main.py clean
```

---

## Commands

| Command | Purpose |
|--------|---------|
| `fetch HASHTAG...` | One-shot scrape → CSV / Excel |
| `watch HASHTAG...` | Continuous monitoring (APScheduler + live Rich table) |
| `stats` | Per-file statistics (record count, unique authors, date range) |
| `clean` | Remove duplicate rows from existing CSVs (with `.bak` backup, `--dry-run`) |
| `config --show` / `--validate` | Print or validate merged configuration |

Run `python main.py <command> --help` for full flag reference.

### Common flags

| Flag | Applies to | Description |
|------|-----------|-------------|
| `--limit N` | `fetch`, `watch` | Max videos per hashtag per run |
| `--format csv\|excel\|both` | `fetch`, `watch` | Output format (default: csv) |
| `--output-dir PATH` | `fetch` | Override output directory |
| `--combined` | `fetch` | Merge all hashtags into a single file |
| `--interval MIN` | `watch` | Recheck interval (5–1440 minutes) |
| `--verbose` | `fetch` | Enable DEBUG-level logging |
| `--config PATH` | all | Path to alternative `config.yaml` |

---

## Output schema (23 fields)

| Field | Type | Notes |
|-------|------|------|
| `video_id` | str | Primary key — used for dedup |
| `url` | str | `https://www.tiktok.com/@user/video/<id>` |
| `description` | str | Video caption |
| `author_username`, `author_display_name` | str | |
| `author_followers`, `author_verified` | int, bool | |
| `likes`, `comments`, `shares`, `views`, `bookmarks` | int | Engagement counters |
| `duration_seconds` | int | |
| `created_at`, `scraped_at` | ISO 8601 | UTC |
| `hashtags` | JSON array (CSV) | From `challenges[].title` |
| `music_id`, `music_title`, `music_author` | str | |
| `source_hashtag` | str | The query that produced this row |
| `language`, `region` | str | 2-letter codes |

CSV files are written with a UTF-8 BOM so Excel opens them without mangling
non-ASCII characters. Excel files get bold headers, A2 freeze pane,
auto-fitted column widths, and clickable URL hyperlinks.

---

## Configuration

Priority (lowest → highest):

1. `AppConfig` dataclass defaults
2. `config.yaml`
3. `.env` (via `python-dotenv`)
4. Environment variables
5. CLI flags

### `config.yaml` excerpt

```yaml
output:
  dir: output
  format: csv          # csv | excel | both
  batch_size: 50

scraping:
  default_limit: 500
  min_delay: 1.5       # seconds between videos (>= 0.5)
  max_delay: 4.0
  max_retries: 5
  base_wait: 30        # exponential backoff base
  max_wait: 300

browser:
  headless: true
  viewport: "1920x1080"

proxy:
  url: null            # "http://user:pass@host:port" or "socks5://..."

monitoring:
  default_interval: 15 # minutes
  default_limit: 50

logging:
  level: INFO
  file: logs/scraper.log
```

### Environment variables

Secrets always belong in `.env`:

| Variable | Purpose |
|---------|---------|
| `TIKTOK_SESSION_ID` | `ms_token` from your logged-in tiktok.com session |
| `TIKTOK_VERIFY_FP` | `verifyFp` cookie |
| `PROXY_URL`, `PROXY_USERNAME`, `PROXY_PASSWORD` | Proxy credentials |
| `OUTPUT_DIR`, `OUTPUT_FORMAT`, `HEADLESS` | Runtime overrides |
| `LOG_LEVEL`, `LOG_FILE` | Logging overrides |
| `WRITE_BATCH_SIZE`, `DEFAULT_LIMIT` | Performance tuning |

---

## Getting a TikTok session

Without a valid session, TikTok's anti-bot layer will block both scrapers
within seconds. To obtain the cookies:

1. Open [tiktok.com](https://www.tiktok.com) in Chrome and log in.
2. DevTools → **Application** → **Cookies** → `https://www.tiktok.com`.
3. Copy the values of `msToken` and `s_v_web_id` / `verifyFp`.
4. Paste into `.env`:
   ```
   TIKTOK_SESSION_ID=<msToken>
   TIKTOK_VERIFY_FP=<verifyFp>
   ```

These cookies expire after a few days — refresh periodically.

---

## Architecture

```
main.py                Click CLI entry point
└── src/
    ├── config.py              Layered config loader + validation
    ├── models.py              VideoRecord, ScraperStats, MonitorJobStatus
    ├── scraper.py             TikTokApi (Playwright) async generator
    ├── fallback_scraper.py    curl_cffi Chrome120 fallback
    ├── storage.py             Buffered CSV/Excel writer + date rotation
    ├── dedup.py               Thread-safe in-memory dedup
    ├── scheduler.py           APScheduler wrapper for `watch` mode
    ├── logger.py              JSON Lines + Rich console logging
    ├── display.py             All Rich terminal UI (panels, tables, live)
    └── utils.py               Shared helpers (dates, paths, formatting)
```

---

## Development

```bash
# Run the test suite (77 tests)
pytest -q

# With coverage
pytest --cov=src --cov-report=term-missing

# Format and lint (if installed)
black src/ tests/
ruff check src/ tests/
```

Tests use pytest fixtures and `tmp_path`; no network calls are made.

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `TikTokApi not installed` | Run `pip install -r requirements.txt` |
| `Executable doesn't exist` (Playwright) | Run `python -m playwright install chromium` |
| `TikTok returned an empty response` | Set `TIKTOK_SESSION_ID` in `.env` or configure a proxy |
| `UnicodeEncodeError` on Windows | Use a Terminal supporting UTF-8 (Windows Terminal, PowerShell 7+) |
| Rate limit errors after many runs | Increase `min_delay` / `max_delay` in `config.yaml` or rotate proxies |

Logs are written to `logs/scraper.log` (JSON Lines) — inspect there for
stack traces and per-record events.

---

## Legal & ethics

This tool uses **unofficial** TikTok endpoints. It is intended for research
and personal use within the bounds of TikTok's [Terms of Service](https://www.tiktok.com/legal/terms-of-service).
You are responsible for:

- Respecting target-site robots policies and rate limits.
- Complying with local data-protection law (GDPR, CCPA, etc.) when storing
  user-generated content.
- Obtaining consent before redistributing personal data.

The authors accept no liability for misuse.

---

## License

[MIT](./LICENSE)

---

## Contributing

Bug reports and pull requests are welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).
