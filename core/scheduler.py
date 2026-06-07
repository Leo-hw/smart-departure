"""Daily schedule planning and due-alert extraction."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent, get_upcoming_events
from core.departure_engine import build_departure_decisions

KST = ZoneInfo("Asia/Seoul")
SCHEDULE_TODAY_PATH = Path(".runtime") / "schedule_today.json"


@dataclass(frozen=True)
class SchedulePlan:
    event_id: str
    summary: str
    location: str
    event_start: datetime
    travel_minutes: int
    is_estimated: bool
    departure_time: datetime
    prep_alert_time: datetime | None
    transport_mode: str
    provider: str
    buffer_minutes: int


@dataclass(frozen=True)
class ScheduledAlert:
    alert_type: str
    alert_time: datetime
    plan: SchedulePlan
    classification: str = "on_time"
    evaluated_at: datetime | None = None

    @property
    def dedup_key(self) -> str:
        return f"{self.plan.event_id}:{self.alert_type}:{self.alert_time.isoformat()}"

    @property
    def event_id(self) -> str:
        return self.plan.event_id

    @property
    def is_late(self) -> bool:
        return self.classification == "catch_up"


def load_or_build_daily_schedule(
    settings: dict[str, Any],
    now: datetime | None = None,
) -> list[SchedulePlan]:
    """Rebuild today's plans unless a configured snapshot TTL allows reuse."""
    current_time = _ensure_kst(now or _current_time_kst())
    snapshot_ttl_minutes = int(
        settings.get("schedule", {}).get("snapshot_ttl_minutes", 0)
    )
    snapshot = _load_schedule_snapshot()
    if _snapshot_is_fresh(snapshot, current_time, snapshot_ttl_minutes):
        return _deserialize_plans(snapshot.get("plans", []))

    plans = build_daily_plans(settings, now=current_time)
    _save_schedule_snapshot(current_time, plans)
    return plans


def build_daily_plans(
    settings: dict[str, Any],
    now: datetime | None = None,
    events: Iterable[CalendarEvent] | None = None,
) -> list[SchedulePlan]:
    """Create today's schedule plans from calendar events and travel times."""
    current_time = _ensure_kst(now or _current_time_kst())
    source_events = list(events) if events is not None else _get_today_events(current_time)
    prep_minutes = int(settings.get("schedule", {}).get("prep_minutes", 0))

    decisions = build_departure_decisions(source_events, now=current_time)
    plans: list[SchedulePlan] = []
    for decision in decisions:
        if decision.event.start_time.date() != current_time.date():
            continue
        prep_alert_time = (
            decision.departure_time - timedelta(minutes=prep_minutes) if prep_minutes > 0 else None
        )
        plans.append(
            SchedulePlan(
                event_id=decision.event.event_id,
                summary=decision.event.summary,
                location=decision.event.location,
                event_start=decision.event.start_time,
                travel_minutes=decision.travel_minutes,
                is_estimated=decision.is_estimated,
                departure_time=decision.departure_time,
                prep_alert_time=prep_alert_time,
                transport_mode=decision.transport_mode,
                provider=decision.provider,
                buffer_minutes=decision.buffer_minutes,
            )
        )

    plans.sort(key=lambda item: item.departure_time)
    return plans


def get_due_alerts(
    plans: Iterable[SchedulePlan],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> list[ScheduledAlert]:
    """Return deliverable alerts, keeping only the latest missed prep stage."""
    candidates = get_alert_candidates(plans, settings=settings, now=now)
    selected, _ = select_latest_prep_alerts(candidates, now=now)
    return selected


def get_alert_candidates(
    plans: Iterable[SchedulePlan],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> list[ScheduledAlert]:
    """Return on-time and catch-up alert candidates before dedup selection."""
    current_time = _ensure_kst(now or _current_time_kst())

    candidates: list[ScheduledAlert] = []
    for plan in plans:
        for prep_alert_time in _get_prep_alert_times(plan):
            alert = ScheduledAlert(alert_type="prep", alert_time=prep_alert_time, plan=plan)
            classification = classify_alert(alert, current_time, settings)
            if classification in {"on_time", "catch_up"}:
                candidates.append(
                    ScheduledAlert(
                        alert_type=alert.alert_type,
                        alert_time=alert.alert_time,
                        plan=alert.plan,
                        classification=classification,
                        evaluated_at=current_time,
                    )
                )

        alert = ScheduledAlert(alert_type="departure", alert_time=plan.departure_time, plan=plan)
        classification = classify_alert(alert, current_time, settings)
        if classification in {"on_time", "catch_up"}:
            candidates.append(
                ScheduledAlert(
                    alert_type=alert.alert_type,
                    alert_time=alert.alert_time,
                    plan=alert.plan,
                    classification=classification,
                    evaluated_at=current_time,
                )
            )

    candidates.sort(key=lambda item: item.alert_time)
    return candidates


def classify_alert(
    alert: ScheduledAlert,
    now: datetime,
    settings: dict[str, Any],
) -> str:
    """Classify an alert relative to its on-time window and catch-up expiry."""
    current_time = _ensure_kst(now)
    target_time = _ensure_kst(alert.alert_time)
    window_minutes = int(settings.get("schedule", {}).get("alert_window_minutes", 0))
    window_delta = timedelta(minutes=window_minutes)
    on_time_start = target_time - window_delta
    on_time_end = target_time + window_delta
    expiry = (
        alert.plan.departure_time
        if alert.alert_type == "prep"
        else alert.plan.departure_time + timedelta(minutes=30)
    )

    if current_time < on_time_start:
        return "pending"
    if current_time <= on_time_end:
        return "on_time"
    if current_time <= expiry:
        return "catch_up"
    return "expired"


def select_latest_prep_alerts(
    alerts: Iterable[ScheduledAlert],
    now: datetime | None = None,
) -> tuple[list[ScheduledAlert], list[ScheduledAlert]]:
    """Select the latest eligible prep per event and seal older prep stages."""
    current_time = _ensure_kst(now or _current_time_kst())
    alerts_list = list(alerts)
    selected: list[ScheduledAlert] = [
        alert
        for alert in alerts_list
        if alert.alert_type != "prep" or alert.alert_time > current_time
    ]
    sealed: list[ScheduledAlert] = []

    prep_by_event: dict[str, list[ScheduledAlert]] = {}
    for alert in alerts_list:
        if alert.alert_type == "prep" and alert.alert_time <= current_time:
            prep_by_event.setdefault(alert.event_id, []).append(alert)

    for event_alerts in prep_by_event.values():
        latest = max(event_alerts, key=lambda item: item.alert_time)
        selected.append(latest)
        sealed.extend(alert for alert in event_alerts if alert is not latest)

    selected.sort(key=lambda item: item.alert_time)
    sealed.sort(key=lambda item: item.alert_time)
    return selected, sealed


def _get_prep_alert_times(plan: SchedulePlan) -> list[datetime]:
    raw_times = getattr(plan, "prep_alert_times", None)
    if raw_times is not None:
        return sorted(
            [_ensure_kst(value) for value in raw_times if isinstance(value, datetime)]
        )
    return [plan.prep_alert_time] if plan.prep_alert_time is not None else []


def _get_today_events(current_time: datetime) -> list[CalendarEvent]:
    end_of_day = datetime.combine(current_time.date(), time.max, tzinfo=KST)
    remaining_seconds = max(0, int((end_of_day - current_time).total_seconds()))
    remaining_hours = max(1, int((remaining_seconds + 3599) / 3600))
    return get_upcoming_events(lookahead_hours=remaining_hours)


def _load_schedule_snapshot() -> dict[str, Any]:
    try:
        with SCHEDULE_TODAY_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _snapshot_is_fresh(
    snapshot: dict[str, Any],
    now: datetime,
    ttl_minutes: int,
) -> bool:
    if ttl_minutes <= 0 or snapshot.get("date") != now.date().isoformat():
        return False

    built_at = snapshot.get("built_at")
    if not isinstance(built_at, str):
        return False

    try:
        built_at_time = _parse_datetime(built_at)
    except ValueError:
        return False

    age = now - built_at_time
    return timedelta(0) <= age <= timedelta(minutes=ttl_minutes)


def _save_schedule_snapshot(built_at: datetime, plans: list[SchedulePlan]) -> None:
    SCHEDULE_TODAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": built_at.date().isoformat(),
        "built_at": built_at.isoformat(),
        "plans": [_serialize_plan(plan) for plan in plans],
    }
    tmp_path = SCHEDULE_TODAY_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(SCHEDULE_TODAY_PATH)


def _serialize_plan(plan: SchedulePlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["event_start"] = plan.event_start.isoformat()
    payload["departure_time"] = plan.departure_time.isoformat()
    payload["prep_alert_time"] = plan.prep_alert_time.isoformat() if plan.prep_alert_time else None
    return payload


def _deserialize_plans(raw_plans: Iterable[dict[str, Any]]) -> list[SchedulePlan]:
    plans: list[SchedulePlan] = []
    for raw_plan in raw_plans:
        if not isinstance(raw_plan, dict):
            continue
        plans.append(
            SchedulePlan(
                event_id=str(raw_plan["event_id"]),
                summary=str(raw_plan["summary"]),
                location=str(raw_plan["location"]),
                event_start=_parse_datetime(str(raw_plan["event_start"])),
                travel_minutes=int(raw_plan["travel_minutes"]),
                is_estimated=bool(raw_plan["is_estimated"]),
                departure_time=_parse_datetime(str(raw_plan["departure_time"])),
                prep_alert_time=(
                    _parse_datetime(str(raw_plan["prep_alert_time"])) if raw_plan.get("prep_alert_time") else None
                ),
                transport_mode=str(raw_plan["transport_mode"]),
                provider=str(raw_plan["provider"]),
                buffer_minutes=int(raw_plan["buffer_minutes"]),
            )
        )
    return plans


def _current_time_kst() -> datetime:
    return datetime.now(tz=KST)


def _ensure_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _parse_datetime(value: str) -> datetime:
    return _ensure_kst(datetime.fromisoformat(value.replace("Z", "+00:00")))
