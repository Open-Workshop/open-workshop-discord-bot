from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_API_URL = "https://api.openworkshop.su"
DEFAULT_WEBSITE_URL = "https://openworkshop.su"
DEFAULT_DIRECT_DOWNLOAD_THRESHOLD_BYTES = 10 * 1024 * 1024
DEFAULT_REQUEST_TIMEOUT_SECONDS = 20.0
DEFAULT_STATISTICS_TIMEOUT_SECONDS = 10.0


class ConfigurationError(RuntimeError):
    """Raised when the bot cannot start because required settings are missing."""


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    api_url: str = DEFAULT_API_URL
    website_url: str = DEFAULT_WEBSITE_URL
    direct_download_threshold_bytes: int = DEFAULT_DIRECT_DOWNLOAD_THRESHOLD_BYTES
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    statistics_timeout_seconds: float = DEFAULT_STATISTICS_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            discord_token=_read_env("DISCORD_TOKEN", ""),
            api_url=_normalized_url(
                _read_env("OPENWORKSHOP_API_URL", DEFAULT_API_URL)
            ),
            website_url=_normalized_url(
                _read_env("OPENWORKSHOP_WEBSITE_URL", DEFAULT_WEBSITE_URL)
            ),
            direct_download_threshold_bytes=_read_int(
                "OPENWORKSHOP_DIRECT_DOWNLOAD_THRESHOLD_BYTES",
                DEFAULT_DIRECT_DOWNLOAD_THRESHOLD_BYTES,
            ),
            request_timeout_seconds=_read_float(
                "OPENWORKSHOP_REQUEST_TIMEOUT_SECONDS",
                DEFAULT_REQUEST_TIMEOUT_SECONDS,
            ),
            statistics_timeout_seconds=_read_float(
                "OPENWORKSHOP_STATISTICS_TIMEOUT_SECONDS",
                DEFAULT_STATISTICS_TIMEOUT_SECONDS,
            ),
        )


def _read_env(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ConfigurationError(f"{name} cannot be empty.")
    return value


def _normalized_url(value: str) -> str:
    return value.rstrip("/")


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer.") from exc

    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return parsed


def _read_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default

    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number.") from exc

    if parsed <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")
    return parsed
