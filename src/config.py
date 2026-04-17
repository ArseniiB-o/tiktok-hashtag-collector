"""Configuration loading and validation for tiktok-hashtag-collector."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigValidationError(Exception):
    """Raised when AppConfig contains invalid values."""


@dataclass
class AppConfig:
    """Application configuration with sensible defaults."""

    # Output
    output_dir: Path = field(default_factory=lambda: Path("output"))
    output_format: str = "csv"          # "csv", "excel", "both"
    write_batch_size: int = 50

    # Scraping behavior
    default_limit: int = 500
    min_delay_seconds: float = 1.5
    max_delay_seconds: float = 4.0
    max_retries: int = 5
    base_wait_seconds: int = 30
    max_wait_seconds: int = 300

    # Browser
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080

    # Proxy (optional)
    proxy_url: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None

    # TikTok session (optional)
    tiktok_session_id: str | None = None
    tiktok_verify_fp: str | None = None

    # Monitoring
    default_interval_minutes: int = 15
    default_monitor_limit: int = 50

    # Logging
    log_level: str = "INFO"
    log_file: Path = field(default_factory=lambda: Path("logs/scraper.log"))
    log_max_bytes: int = 10_485_760   # 10 MB
    log_backup_count: int = 5


def _get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict keys, returning *default* if any key is missing."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def _parse_viewport(value: str) -> tuple[int, int]:
    """Parse a viewport string like '1920x1080' into (width, height).

    Raises:
        ConfigValidationError: If the string is not in WxH format.
    """
    parts = value.lower().split("x")
    if len(parts) != 2:
        raise ConfigValidationError(
            f"Invalid viewport format '{value}'. Expected 'WIDTHxHEIGHT', e.g. '1920x1080'."
        )
    try:
        width, height = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ConfigValidationError(
            f"Viewport dimensions must be integers, got '{value}'."
        ) from exc
    return width, height


def _apply_yaml(config: AppConfig, yaml_data: dict[str, Any]) -> None:
    """Mutate *config* in-place with values from a parsed YAML mapping."""

    # output.*
    output = yaml_data.get("output", {})
    if (val := output.get("dir")) is not None:
        config.output_dir = Path(val)
    if (val := output.get("format")) is not None:
        config.output_format = str(val)
    if (val := output.get("batch_size")) is not None:
        config.write_batch_size = int(val)

    # scraping.*
    scraping = yaml_data.get("scraping", {})
    if (val := scraping.get("default_limit")) is not None:
        config.default_limit = int(val)
    if (val := scraping.get("min_delay")) is not None:
        config.min_delay_seconds = float(val)
    if (val := scraping.get("max_delay")) is not None:
        config.max_delay_seconds = float(val)
    if (val := scraping.get("max_retries")) is not None:
        config.max_retries = int(val)
    if (val := scraping.get("base_wait")) is not None:
        config.base_wait_seconds = int(val)
    if (val := scraping.get("max_wait")) is not None:
        config.max_wait_seconds = int(val)

    # browser.*
    browser = yaml_data.get("browser", {})
    if (val := browser.get("headless")) is not None:
        config.headless = bool(val)
    if (val := browser.get("viewport")) is not None:
        config.viewport_width, config.viewport_height = _parse_viewport(str(val))

    # proxy.*
    proxy = yaml_data.get("proxy", {})
    if (val := proxy.get("url")) is not None:
        config.proxy_url = str(val)
    if (val := proxy.get("username")) is not None:
        config.proxy_username = str(val)
    if (val := proxy.get("password")) is not None:
        config.proxy_password = str(val)

    # tiktok.*
    tiktok = yaml_data.get("tiktok", {})
    if (val := tiktok.get("session_id")) is not None:
        config.tiktok_session_id = str(val)
    if (val := tiktok.get("verify_fp")) is not None:
        config.tiktok_verify_fp = str(val)

    # monitoring.*
    monitoring = yaml_data.get("monitoring", {})
    if (val := monitoring.get("default_interval")) is not None:
        config.default_interval_minutes = int(val)
    if (val := monitoring.get("default_limit")) is not None:
        config.default_monitor_limit = int(val)

    # logging.*
    logging_cfg = yaml_data.get("logging", {})
    if (val := logging_cfg.get("level")) is not None:
        config.log_level = str(val).upper()
    if (val := logging_cfg.get("file")) is not None:
        config.log_file = Path(val)


_TRUE_LITERALS: frozenset[str] = frozenset({"1", "true", "yes", "on"})
_FALSE_LITERALS: frozenset[str] = frozenset({"0", "false", "no", "off"})


def _parse_bool(value: str) -> bool | None:
    """Parse a string env value as bool. Returns None if unrecognised."""
    v = value.strip().lower()
    if v in _TRUE_LITERALS:
        return True
    if v in _FALSE_LITERALS:
        return False
    return None


def _apply_env_vars(config: AppConfig) -> None:
    """Override selected config fields from environment variables."""
    str_map: dict[str, str] = {
        "TIKTOK_SESSION_ID": "tiktok_session_id",
        "TIKTOK_VERIFY_FP": "tiktok_verify_fp",
        "PROXY_URL": "proxy_url",
        "PROXY_USERNAME": "proxy_username",
        "PROXY_PASSWORD": "proxy_password",
    }
    for env_key, attr in str_map.items():
        value = os.environ.get(env_key)
        if value is not None:
            setattr(config, attr, value)

    # Scalar overrides
    if (val := os.environ.get("OUTPUT_DIR")) is not None:
        config.output_dir = Path(val)
    if (val := os.environ.get("OUTPUT_FORMAT")) is not None:
        config.output_format = val.strip().lower()
    if (val := os.environ.get("LOG_LEVEL")) is not None:
        config.log_level = val.strip().upper()
    if (val := os.environ.get("LOG_FILE")) is not None:
        config.log_file = Path(val)
    if (val := os.environ.get("HEADLESS")) is not None:
        parsed = _parse_bool(val)
        if parsed is not None:
            config.headless = parsed
    if (val := os.environ.get("WRITE_BATCH_SIZE")) is not None:
        try:
            config.write_batch_size = int(val)
        except ValueError:
            pass
    if (val := os.environ.get("DEFAULT_LIMIT")) is not None:
        try:
            config.default_limit = int(val)
        except ValueError:
            pass


def validate_config(config: AppConfig) -> None:
    """Validate all fields of *config*.

    Raises:
        ConfigValidationError: On the first validation failure encountered.
    """
    valid_formats = {"csv", "excel", "both"}
    if config.output_format not in valid_formats:
        raise ConfigValidationError(
            f"output_format must be one of {sorted(valid_formats)}, got '{config.output_format}'."
        )

    if config.min_delay_seconds < 0.5:
        raise ConfigValidationError(
            f"min_delay_seconds must be >= 0.5 (floor enforced), got {config.min_delay_seconds}."
        )

    if config.min_delay_seconds >= config.max_delay_seconds:
        raise ConfigValidationError(
            f"min_delay_seconds ({config.min_delay_seconds}) must be less than "
            f"max_delay_seconds ({config.max_delay_seconds})."
        )

    if config.base_wait_seconds <= 0:
        raise ConfigValidationError(
            f"base_wait_seconds must be > 0, got {config.base_wait_seconds}."
        )

    if config.base_wait_seconds >= config.max_wait_seconds:
        raise ConfigValidationError(
            f"base_wait_seconds ({config.base_wait_seconds}) must be less than "
            f"max_wait_seconds ({config.max_wait_seconds})."
        )

    if config.max_retries <= 0:
        raise ConfigValidationError(
            f"max_retries must be > 0, got {config.max_retries}."
        )

    if config.viewport_width <= 0 or config.viewport_height <= 0:
        raise ConfigValidationError(
            f"viewport dimensions must be positive, got "
            f"{config.viewport_width}x{config.viewport_height}."
        )

    if config.log_max_bytes <= 0:
        raise ConfigValidationError(
            f"log_max_bytes must be > 0, got {config.log_max_bytes}."
        )

    if config.log_backup_count < 0:
        raise ConfigValidationError(
            f"log_backup_count must be >= 0, got {config.log_backup_count}."
        )

    if config.write_batch_size <= 0:
        raise ConfigValidationError(
            f"write_batch_size must be > 0, got {config.write_batch_size}."
        )

    if config.default_limit <= 0:
        raise ConfigValidationError(
            f"default_limit must be > 0, got {config.default_limit}."
        )

    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if config.log_level not in valid_levels:
        raise ConfigValidationError(
            f"log_level must be one of {sorted(valid_levels)}, got '{config.log_level}'."
        )

    if config.default_interval_minutes < 5:
        raise ConfigValidationError(
            f"default_interval_minutes must be >= 5, got {config.default_interval_minutes}."
        )

    if config.proxy_url is not None:
        valid_schemes = ("http://", "https://", "socks5://")
        if not any(config.proxy_url.startswith(scheme) for scheme in valid_schemes):
            raise ConfigValidationError(
                f"proxy_url must start with one of {valid_schemes}, got '{config.proxy_url}'."
            )


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load application configuration from defaults, YAML, .env, and environment variables.

    Priority (lowest → highest):
    1. AppConfig dataclass defaults
    2. config.yaml (from *config_path* or ``Path("config.yaml")``)
    3. .env file values (via python-dotenv)
    4. Environment variables (override .env)
    5. CLI flags — NOT handled here; apply those in main.py after calling this function.

    Args:
        config_path: Optional explicit path to the YAML config file.
                     Defaults to ``Path("config.yaml")`` in the current directory.

    Returns:
        A fully validated :class:`AppConfig` instance.

    Raises:
        ConfigValidationError: If the resolved configuration is invalid.
    """
    # Step 1 — load .env from project root (populates os.environ; existing env vars are NOT overwritten)
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv()  # fallback to CWD search

    # Step 2 — start from dataclass defaults
    config = AppConfig()

    # Step 3 — overlay YAML values
    yaml_file = config_path if config_path is not None else Path("config.yaml")
    if yaml_file.exists():
        try:
            with yaml_file.open("r", encoding="utf-8") as fh:
                yaml_data: Any = yaml.safe_load(fh)
            if isinstance(yaml_data, dict):
                _apply_yaml(config, yaml_data)
        except (yaml.YAMLError, OSError) as e:
            raise ConfigValidationError(f"Failed to read config file '{yaml_file}': {e}") from e

    # Step 4 — override with environment variables
    _apply_env_vars(config)

    # Step 5 — validate before returning
    validate_config(config)

    return config
