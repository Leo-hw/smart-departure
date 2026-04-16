"""Application entrypoint for Railway cron execution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.dedup import filter_pending_decisions, mark_successful_deliveries
from core.departure_engine import evaluate_departure_alert
from core.notifier import send_notifications
from shared.config.runtime_config import load_dotenv_file, load_settings, validate_environment

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "shared" / "config" / "settings.yaml"
RUNTIME_DIR = BASE_DIR / ".runtime"


def ensure_runtime_dir() -> None:
    """Create local runtime storage for dedup and caches."""
    RUNTIME_DIR.mkdir(exist_ok=True)


def main() -> int:
    try:
        load_dotenv_file()
        settings = load_settings()
        env = validate_environment(settings)
        ensure_runtime_dir()
        alertable_decisions = evaluate_departure_alert()
        pending_decisions, skipped_decisions = filter_pending_decisions(alertable_decisions, settings=settings)
        deliveries = send_notifications(pending_decisions, settings=settings)
        successful_event_ids = {item.event_id for item in deliveries if item.success}
        successful_decisions = [
            decision for decision in pending_decisions if decision.event.event_id in successful_event_ids
        ]
        if successful_decisions:
            mark_successful_deliveries(successful_decisions, settings=settings)
    except Exception as exc:  # pragma: no cover - CLI bootstrap path
        print(f"[smart-departure] startup failed: {exc}", file=sys.stderr)
        return 1

    calendars = [item.strip() for item in env["GOOGLE_CALENDAR_IDS"].split(",") if item.strip()]
    print("[smart-departure] bootstrap ready")
    print(f"Loaded settings from: {SETTINGS_PATH}")
    print(f"Configured calendar IDs: {len(calendars)}")
    print(f"Default transport: {settings['user'].get('default_transport', 'transit')}")
    print(f"Alertable events: {len(alertable_decisions)}")
    print(f"Dedup skipped events: {len(skipped_decisions)}")
    print(f"Notifications attempted: {len(deliveries)}")
    failed_deliveries = [item for item in deliveries if not item.success]
    if failed_deliveries:
        for delivery in failed_deliveries:
            print(
                f"[smart-departure] delivery failed: channel={delivery.channel} "
                f"event_id={delivery.event_id} error={delivery.error}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
