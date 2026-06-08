"""Application entrypoint for scheduled departure checks."""

from __future__ import annotations

import sys
from pathlib import Path

from core.dedup import (
    filter_pending_decisions,
    mark_skipped_deliveries,
    mark_successful_deliveries,
)
from core.notifier import send_failure_notification, send_notifications
from core.privacy import safe_exception_label, short_id
from core.scheduler import (
    get_alert_candidates,
    load_or_build_daily_schedule,
    select_latest_prep_alerts,
)
from shared.config.runtime_config import load_dotenv_file, load_settings, validate_environment

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "shared" / "config" / "settings.yaml"
RUNTIME_DIR = BASE_DIR / ".runtime"


def ensure_runtime_dir() -> None:
    """Create local runtime storage for schedules, dedup, and caches."""
    RUNTIME_DIR.mkdir(exist_ok=True)


def main() -> int:
    settings = None
    try:
        load_dotenv_file()
        settings = load_settings()
        env = validate_environment(settings)
        ensure_runtime_dir()
        plans = load_or_build_daily_schedule(settings)
        alert_candidates = get_alert_candidates(plans, settings=settings)
        pending_candidates, dedup_skipped_alerts = filter_pending_decisions(
            alert_candidates,
            settings=settings,
        )
        pending_alerts, sealed_alerts = select_latest_prep_alerts(pending_candidates)
        if sealed_alerts:
            mark_skipped_deliveries(sealed_alerts, settings=settings)
        deliveries = send_notifications(pending_alerts, settings=settings)
        successful_keys = {item.dedup_key for item in deliveries if item.success}
        successful_alerts = [
            alert for alert in pending_alerts if alert.dedup_key in successful_keys
        ]
        if successful_alerts:
            mark_successful_deliveries(successful_alerts, settings=settings)
    except Exception as exc:  # pragma: no cover - CLI bootstrap path
        print(
            "[smart-departure] startup failed: "
            f"{safe_exception_label(exc)}",
            file=sys.stderr,
        )
        try:
            failure_delivery = send_failure_notification(exc, settings=settings)
            if not failure_delivery.success:
                print(
                    "[smart-departure] failure notification failed: "
                    f"{failure_delivery.error or 'unknown error'}",
                    file=sys.stderr,
                )
        except Exception as notification_exc:
            print(
                "[smart-departure] failure notification failed: "
                f"{safe_exception_label(notification_exc)}",
                file=sys.stderr,
            )
        return 1

    calendars = [item.strip() for item in env["GOOGLE_CALENDAR_IDS"].split(",") if item.strip()]
    print("[smart-departure] bootstrap ready")
    print("Loaded settings from: shared/config/settings.yaml")
    print(f"Configured calendar IDs: {len(calendars)}")
    print(f"Default transport: {settings['user'].get('default_transport', 'transit')}")
    print(f"Today's plans: {len(plans)}")
    for plan in plans:
        prep_time = plan.prep_alert_time.strftime("%Y-%m-%d %H:%M") if plan.prep_alert_time else "disabled"
        print(
            "[smart-departure] plan "
            f"event_id={short_id(plan.event_id)} "
            f"start={plan.event_start.strftime('%Y-%m-%d %H:%M')} "
            f"prep={prep_time} "
            f"departure={plan.departure_time.strftime('%Y-%m-%d %H:%M')} "
            f"travel={plan.travel_minutes}m provider={plan.provider} "
            f"estimated={plan.is_estimated}"
        )
    print(f"Due alerts: {len(pending_alerts)}")
    for alert in pending_alerts:
        print(
            "[smart-departure] due "
            f"type={alert.alert_type} event_id={short_id(alert.event_id)} "
            f"alert_time={alert.alert_time.strftime('%Y-%m-%d %H:%M')} "
            f"classification={alert.classification}"
        )
    print(f"Dedup skipped events: {len(dedup_skipped_alerts)}")
    print(f"Sealed prep alerts: {len(sealed_alerts)}")
    print(f"Notifications attempted: {len(deliveries)}")
    failed_deliveries = [item for item in deliveries if not item.success]
    if failed_deliveries:
        for delivery in failed_deliveries:
            print(
                f"[smart-departure] delivery failed: channel={delivery.channel} "
                f"event_id={short_id(delivery.event_id)} "
                f"error={delivery.error or 'unknown error'}",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
