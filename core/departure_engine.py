"""Departure calculation and alert decision engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent, get_upcoming_events
from core.maps_service import get_travel_time
from shared.config.runtime_config import load_settings

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class DepartureDecision:
    event: CalendarEvent
    transport_mode: str
    travel_minutes: int
    buffer_minutes: int
    departure_time: datetime
    should_alert: bool
    is_estimated: bool
    provider: str


def build_departure_decisions(
    events: Iterable[CalendarEvent],
    now: datetime | None = None,
) -> list[DepartureDecision]:
    """Build departure decisions for the provided events."""
    settings = load_settings()
    now_kst = _ensure_kst(now or _current_time_kst())
    home_address = str(settings.get("user", {}).get("home_address", "")).strip()
    if not home_address:
        raise RuntimeError("HOME_ADDRESS is required to calculate departure times")

    default_transport = str(settings.get("user", {}).get("default_transport", "transit")).strip() or "transit"
    alert_window_minutes = int(settings.get("schedule", {}).get("alert_window_minutes", 0))
    transport_settings = settings.get("transport", {})

    decisions: list[DepartureDecision] = []
    for event in events:
        transport_mode = event.transport_override or default_transport
        buffer_minutes = int(transport_settings.get(transport_mode, {}).get("buffer_minutes", 0))
        travel_result = get_travel_time(home_address, event.location, transport_mode)
        departure_time = event.start_time - timedelta(
            minutes=travel_result.duration_minutes + buffer_minutes
        )
        should_alert = _is_within_alert_window(departure_time, now_kst, alert_window_minutes)
        decisions.append(
            DepartureDecision(
                event=event,
                transport_mode=transport_mode,
                travel_minutes=travel_result.duration_minutes,
                buffer_minutes=buffer_minutes,
                departure_time=departure_time,
                should_alert=should_alert,
                is_estimated=travel_result.is_estimated,
                provider=travel_result.provider,
            )
        )

    decisions.sort(key=lambda item: item.departure_time)
    return decisions


def evaluate_departure_alert(
    events: Iterable[CalendarEvent] | None = None,
    now: datetime | None = None,
) -> list[DepartureDecision]:
    """Return only the events that are currently inside the alert window."""
    source_events = list(events) if events is not None else get_upcoming_events()
    return [item for item in build_departure_decisions(source_events, now=now) if item.should_alert]


def _current_time_kst() -> datetime:
    return datetime.now(tz=KST)


def _ensure_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _is_within_alert_window(
    departure_time: datetime,
    now: datetime,
    alert_window_minutes: int,
) -> bool:
    window_delta = timedelta(minutes=alert_window_minutes)
    return abs(now - departure_time) <= window_delta
