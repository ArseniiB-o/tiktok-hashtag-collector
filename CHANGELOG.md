# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-04-17

### Added
- One-shot `fetch` command with per-hashtag progress bar and run summary.
- Continuous `watch` command using APScheduler with live Rich status table.
- `stats` command — per-file record counts, unique authors, and date range.
- `clean` command — deduplicate existing CSVs with automatic `.bak` backup.
- `config --show` / `--validate` command for merged configuration inspection.
- Dual scraper backends:
  - Primary: `TikTokApi` over Playwright Chromium.
  - Fallback: `curl_cffi` session impersonating Chrome 120 TLS fingerprint.
- 23-field `VideoRecord` schema (IDs, URLs, author, engagement, music, hashtags,
  language, region, timestamps).
- CSV output with UTF-8 BOM (Excel-friendly) and optional `.xlsx` with bold
  headers, frozen panes, auto-widths, and clickable URL hyperlinks.
- Thread-safe in-memory deduplication, pre-loaded from existing output files.
- Daily file rotation — new file created when the UTC date advances.
- Layered configuration: dataclass defaults → `config.yaml` → `.env` → env vars
  → CLI flags.
- Anti-bot measures: 10 rotating User-Agents, randomised delays, exponential
  backoff on rate limits, HTTP/HTTPS/SOCKS5 proxy support.
- JSON Lines rotating log (10 MB × 5) + Rich console output.
- Windows cp125x terminal support via forced UTF-8 stdout and
  `legacy_windows=False`.
- 77 pytest unit and integration tests (no network calls).

[Unreleased]: https://github.com/ArseniiB-o/tiktok-hashtag-collector/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ArseniiB-o/tiktok-hashtag-collector/releases/tag/v1.0.0
