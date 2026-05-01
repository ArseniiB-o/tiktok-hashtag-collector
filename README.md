# TikTok Hashtag Collector

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![Status: Beta](https://img.shields.io/badge/status-beta-yellow.svg)](./CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-77%20passing%20%2F%2030%25%20coverage-yellow.svg)](./tests)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A zero-cloud, locally-running Python CLI that harvests TikTok video metadata by
hashtag and streams results to **CSV / Excel** with dedup, date rotation, live
monitoring, and a Rich-powered terminal UI.

Intended audience: **academic researchers under institutional ethics review**
who need reproducible TikTok metadata samples for documented research purposes.
Not intended for commercial scraping, marketing, or bulk surveillance.

> ⚠️ **Beta software on a fragile foundation.** This tool depends on
> unofficial reverse-engineered TikTok endpoints and on the upstream
> [`TikTokApi`](https://github.com/davidteather/TikTok-Api) library, which
> the upstream maintainer documents as routinely broken by TikTok's anti-bot
> changes. Empty responses, captchas, and IP/account blocks are expected,
> not exceptional.

---

## ⚖️ Legal & ethical use — read before running

**By running this tool you become a data controller under EU/UK data
protection law.** TikTok video metadata includes personal data
(`author_username`, `author_display_name`, `author_followers`, free-text
`description`) attributable to identifiable natural persons. You — not the
authors of this software — are legally responsible for every byte you collect.

Before running this project you must:

1. **Confirm you have a lawful basis** for processing under GDPR Art. 6 / UK
   GDPR. "I'm curious" is not a lawful basis. Recognised bases include
   research carried out under documented institutional ethics approval
   (GDPR Art. 89), journalism in the public interest, or your own legal
   obligation. Without a lawful basis, do not run this tool.
2. **Apply data minimisation.** Drop columns you do not need. Anonymise or
   pseudonymise as early as possible. Do not retain raw datasets longer
   than your stated research purpose requires.
3. **Respect [TikTok's Terms of Service](https://www.tiktok.com/legal/terms-of-service).**
   Section 5 prohibits automated data collection. Using this tool likely
   places you in breach of that contract regardless of your local law.
4. **Comply with rate limits and robots policies.** Do not increase the
   defaults to overwhelm any infrastructure.
5. **Be aware of jurisdiction.** EU/EEA/UK residents face direct exposure
   to data protection authorities (BfDI, ICO, your state-level DPA, …).
   Penalties apply to natural persons as well as companies.
6. **Do not redistribute** scraped personal data — derived statistics
   only, after aggregation and anonymisation.

**The MIT licence covers the software, not your processing activity.** If
any of the above is unclear, consult a qualified data protection lawyer in
your jurisdiction before proceeding. The authors accept no liability for
misuse, but this disclaimer does **not** transfer your obligations as a
controller back onto them — those obligations remain yours.

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
- **Anti-bot mitigations** — 10 rotating User-Agents, randomised per-video
  delays, optional HTTP / HTTPS / SOCKS5 proxy. (Earlier docs claimed
  "exponential back-off on rate limits" via `tenacity`; that integration
  was never implemented and the dependency was removed in the current
  release. Failures from TikTok currently surface immediately.)
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

## Output schema (22 fields)

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

Cell values that begin with `=`, `+`, `-`, `@`, `\t`, or `\r` are prefixed
with a single quote before write to defuse spreadsheet formula injection
(see [OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection)).
TikTok descriptions in the wild are arbitrary user input and have been
observed carrying such payloads.

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

## Known limitations

- **Test coverage is 30%.** The `scraper.py`, `fallback_scraper.py`,
  `scheduler.py`, and `display.py` modules are not yet covered by unit
  tests. The 77 passing tests cover `dedup`, `models`, `storage`, `utils`,
  and parts of `config`/`logger`. Treat the scraping path as not regression-
  protected.
- **Upstream `TikTokApi` is documented as fragile.** Empty responses are
  the upstream's first listed troubleshooting entry. Plan accordingly.
- **No retry/back-off.** Earlier versions advertised exponential back-off
  via `tenacity`, but that integration was never wired up; both have been
  removed from dependencies in this release. Failures surface immediately.
- **Single-process dedup.** The dedup store is in-memory; concurrent
  processes pointed at the same output directory will not coordinate.
- **No checkpointing.** A long fetch interrupted at record N restarts from
  the beginning; rows already on disk are skipped via `load_existing`, but
  pagination cursors are not persisted.

For the full review that produced this list, see the project notes; a
contributor audit is welcome.

---

## License

[MIT](./LICENSE)

---

## Contributing

Bug reports and pull requests are welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md).
