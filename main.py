"""Application entrypoint for scheduled departure checks."""

from __future__ import annotations

import sys
from pathlib import Path

from core.dedup import filter_pending_decisions, mark_successful_deliveries
from core.notifier import send_notifications
from core.scheduler import get_due_alerts, load_or_build_daily_schedule
from shared.config.runtime_config import load_dotenv_file, load_settings, validate_environment

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "shared" / "config" / "settings.yaml"
RUNTIME_DIR = BASE_DIR / ".runtime"


def ensure_runtime_dir() -> None:
    """Create local runtime storage for schedules, dedup, and caches."""
    RUNTIME_DIR.mkdir(exist_ok=True)


def main() -> int:
    try:
        load_dotenv_file()
        settings = load_settings()
        env = validate_environment(settings)
        ensure_runtime_dir()
        plans = load_or_build_daily_schedule(settings)
        due_alerts = get_due_alerts(plans, settings=settings)
        pending_alerts, skipped_alerts = filter_pending_decisions(due_alerts, settings=settings)
        deliveries = send_notifications(pending_alerts, settings=settings)
        successful_event_ids = {item.event_id for item in deliveries if item.success}
        successful_alerts = [alert for alert in pending_alerts if alert.event_id in successful_event_ids]
        if successful_alerts:
            mark_successful_deliveries(successful_alerts, settings=settings)
    except Exception as exc:  # pragma: no cover - CLI bootstrap path
        print(f"[smart-departure] startup failed: {exc}", file=sys.stderr)
        return 1

    calendars = [item.strip() for item in env["GOOGLE_CALENDAR_IDS"].split(",") if item.strip()]
    print("[smart-departure] bootstrap ready")
    print(f"Loaded settings from: {SETTINGS_PATH}")
    print(f"Configured calendar IDs: {len(calendars)}")
    print(f"Default transport: {settings['user'].get('default_transport', 'transit')}")
    print(f"Today's plans: {len(plans)}")
    print(f"Due alerts: {len(due_alerts)}")
    print(f"Dedup skipped events: {len(skipped_alerts)}")
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
