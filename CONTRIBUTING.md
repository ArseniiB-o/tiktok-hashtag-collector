# Contributing to TikTok Hashtag Collector

Thanks for your interest in contributing! This document outlines the process for
filing issues, proposing changes, and submitting pull requests.

## Code of Conduct

Be respectful. Assume good faith. No harassment, discrimination, or personal
attacks.

## Getting set up

```bash
git clone https://github.com/<your-fork>/tiktok-hashtag-collector.git
cd tiktok-hashtag-collector

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install chromium
```

## Running tests

```bash
pytest -q                                 # fast run
pytest --cov=src --cov-report=term-missing  # with coverage
```

Tests must pass on Python 3.11 and 3.12, and on Linux, macOS, and Windows (the
CI matrix covers all six combinations).

## Code style

- **black** — formatter (line length 100)
- **ruff** — linter
- **mypy** — optional static typing (not enforced)

Run locally before opening a PR:

```bash
black src/ tests/ main.py
ruff check --fix src/ tests/ main.py
```

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add --proxy-rotate flag for watch mode
fix: handle cp1251 terminal encoding on Windows
docs: clarify TIKTOK_SESSION_ID instructions in README
test: cover dedup thread-safety under high contention
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `perf`, `ci`.

## Pull request checklist

- [ ] Tests added or updated for the behavior change
- [ ] `pytest` passes locally
- [ ] `ruff check` and `black --check` pass
- [ ] README / config docs updated if behavior or flags changed
- [ ] No secrets committed (`.env`, cookies, proxy credentials)
- [ ] CHANGELOG entry under `[Unreleased]`

## Filing an issue

Open a GitHub issue using one of the templates:

- **Bug report** — include Python version, OS, full command, error traceback
- **Feature request** — describe the use case and proposed interface

## Security

Do **not** file public issues for security vulnerabilities. Instead, email the
maintainer (see repository profile) with a minimal reproduction.

## Scope

This tool uses unofficial TikTok endpoints. PRs that materially expand the
surface area (e.g., new endpoints, authenticated mutations, login automation)
will be scrutinized against the project's research-focused, read-only mission.
