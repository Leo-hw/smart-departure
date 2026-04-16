"""Runtime configuration loading and environment validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
SETTINGS_PATH = BASE_DIR / "shared" / "config" / "settings.yaml"
ENV_PATH = BASE_DIR / ".env"

BASE_REQUIRED_ENV_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_CALENDAR_IDS",
    "GOOGLE_MAPS_API_KEY",
    "HOME_ADDRESS",
]

CHANNEL_REQUIRED_ENV_VARS = {
    "discord": ["DISCORD_WEBHOOK_URL"],
    "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
}


def load_settings() -> dict[str, Any]:
    """Load YAML settings and apply environment overrides."""
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")

    settings = _read_yaml_settings(SETTINGS_PATH)
    user_settings = settings.setdefault("user", {})
    notification_settings = settings.setdefault("notification", {})
    notification_settings.setdefault("enabled_channels", ["discord"])
    notification_settings.setdefault("discord", {})
    notification_settings.setdefault("telegram", {})

    home_address = os.environ.get("HOME_ADDRESS")
    if home_address:
        user_settings["home_address"] = home_address

    return settings


def load_dotenv_file(path: Path | None = None) -> None:
    """Load a local .env file into os.environ without overriding exported values."""
    env_path = path or ENV_PATH
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if value.startswith(("\"", "'")) and value.endswith(("\"", "'")):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def get_enabled_channels(settings: dict[str, Any]) -> list[str]:
    """Return validated notification channels from settings."""
    raw_channels = settings.get("notification", {}).get("enabled_channels", [])
    if isinstance(raw_channels, str):
        raw_channels = [raw_channels]

    channels: list[str] = []
    for raw_channel in raw_channels:
        channel = str(raw_channel).strip().lower()
        if channel and channel not in channels:
            channels.append(channel)
    return channels


def validate_environment(settings: dict[str, Any]) -> dict[str, str]:
    """Return required environment values based on active notification channels."""
    enabled_channels = get_enabled_channels(settings)
    unsupported_channels = [channel for channel in enabled_channels if channel not in CHANNEL_REQUIRED_ENV_VARS]
    if unsupported_channels:
        raise RuntimeError("Unsupported notification channels: " + ", ".join(unsupported_channels))

    required_vars = list(BASE_REQUIRED_ENV_VARS)
    for channel in enabled_channels:
        required_vars.extend(CHANNEL_REQUIRED_ENV_VARS.get(channel, []))

    missing = [name for name in required_vars if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(sorted(set(missing))))

    return {name: os.environ[name] for name in sorted(set(required_vars))}


def _read_yaml_settings(path: Path) -> dict[str, Any]:
    """Load YAML with PyYAML when available and a minimal fallback otherwise."""
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return _parse_simple_yaml(path.read_text(encoding="utf-8"))

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _parse_simple_yaml(raw_text: str) -> dict[str, Any]:
    """Parse the limited nested mapping structure used by settings.yaml."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in raw_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if ":" not in stripped:
            raise ValueError(f"Unsupported YAML line: {stripped}")

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()

        parent = stack[-1][1]
        if value == "":
            container: dict[str, Any] = {}
            parent[key] = container
            stack.append((indent, container))
            continue

        parent[key] = _coerce_scalar(value)

    return root


def _coerce_scalar(value: str) -> Any:
    """Convert simple YAML scalars into Python values."""
    cleaned = value.split("  #", 1)[0].strip()
    if cleaned.startswith(("\"", "'")) and cleaned.endswith(("\"", "'")):
        return cleaned[1:-1]
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned.startswith("[") and cleaned.endswith("]"):
        return [item.strip().strip("'\"") for item in cleaned[1:-1].split(",") if item.strip()]
    return cleaned
