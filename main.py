"""Application entrypoint for Railway cron execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REQUIRED_ENV_VARS = [
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "GOOGLE_CALENDAR_IDS",
    "GOOGLE_MAPS_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "HOME_ADDRESS",
]

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "shared" / "config" / "settings.yaml"
RUNTIME_DIR = BASE_DIR / ".runtime"


def validate_environment() -> dict[str, str]:
    """Return required environment values or raise a readable error."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        message = "Missing required environment variables: " + ", ".join(missing)
        raise RuntimeError(message)
    return {name: os.environ[name] for name in REQUIRED_ENV_VARS}


def load_settings() -> dict:
    """Load YAML settings and apply environment overrides."""
    if not SETTINGS_PATH.exists():
        raise FileNotFoundError(f"Settings file not found: {SETTINGS_PATH}")

    settings = _read_yaml_settings(SETTINGS_PATH)

    user_settings = settings.setdefault("user", {})
    home_address = os.environ.get("HOME_ADDRESS")
    if home_address:
        user_settings["home_address"] = home_address

    return settings


def ensure_runtime_dir() -> None:
    """Create local runtime storage for dedup and caches."""
    RUNTIME_DIR.mkdir(exist_ok=True)


def _read_yaml_settings(path: Path) -> dict:
    """Load YAML with PyYAML when available and a minimal fallback otherwise."""
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return _parse_simple_yaml(path.read_text(encoding="utf-8"))

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _parse_simple_yaml(raw_text: str) -> dict:
    """Parse the limited nested mapping structure used by settings.yaml."""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]

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
            container: dict = {}
            parent[key] = container
            stack.append((indent, container))
            continue

        parent[key] = _coerce_scalar(value)

    return root


def _coerce_scalar(value: str):
    """Convert simple YAML scalars into Python values."""
    cleaned = value.split("  #", 1)[0].strip()
    if cleaned.startswith(("\"", "'")) and cleaned.endswith(("\"", "'")):
        return cleaned[1:-1]
    if cleaned.isdigit():
        return int(cleaned)
    return cleaned


def main() -> int:
    try:
        env = validate_environment()
        settings = load_settings()
        ensure_runtime_dir()
    except Exception as exc:  # pragma: no cover - CLI bootstrap path
        print(f"[smart-departure] startup failed: {exc}", file=sys.stderr)
        return 1

    calendars = [item.strip() for item in env["GOOGLE_CALENDAR_IDS"].split(",") if item.strip()]
    print("[smart-departure] bootstrap ready")
    print(f"Loaded settings from: {SETTINGS_PATH}")
    print(f"Configured calendar IDs: {len(calendars)}")
    print(f"Default transport: {settings['user'].get('default_transport', 'transit')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
