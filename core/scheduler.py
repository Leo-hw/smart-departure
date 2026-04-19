"""Daily schedule planning and due-alert extraction."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
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

    @property
    def dedup_key(self) -> str:
        return f"{self.plan.event_id}:{self.alert_type}:{self.alert_time.isoformat()}"

    @property
    def event_id(self) -> str:
        return self.plan.event_id


def load_or_build_daily_schedule(
    settings: dict[str, Any],
    now: datetime | None = None,
) -> list[SchedulePlan]:
    """Load today's plans from cache or rebuild them."""
    current_time = _ensure_kst(now or _current_time_kst())
    snapshot = _load_schedule_snapshot()
    if snapshot.get("date") == current_time.date().isoformat():
        return _deserialize_plans(snapshot.get("plans", []))

    plans = build_daily_plans(settings, now=current_time)
    _save_schedule_snapshot(current_time.date(), plans)
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
    """Return prep/departure alerts due within the current alert window."""
    current_time = _ensure_kst(now or _current_time_kst())
    alert_window_minutes = int(settings.get("schedule", {}).get("alert_window_minutes", 0))
    window_delta = timedelta(minutes=alert_window_minutes)

    due_alerts: list[ScheduledAlert] = []
    for plan in plans:
        if plan.prep_alert_time is not None and abs(current_time - plan.prep_alert_time) <= window_delta:
            due_alerts.append(ScheduledAlert(alert_type="prep", alert_time=plan.prep_alert_time, plan=plan))
        if abs(current_time - plan.departure_time) <= window_delta:
            due_alerts.append(
                ScheduledAlert(alert_type="departure", alert_time=plan.departure_time, plan=plan)
            )

    due_alerts.sort(key=lambda item: item.alert_time)
    return due_alerts


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


def _save_schedule_snapshot(schedule_date: date, plans: list[SchedulePlan]) -> None:
    SCHEDULE_TODAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": schedule_date.isoformat(),
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
