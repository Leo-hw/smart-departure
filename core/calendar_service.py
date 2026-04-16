"""Google Calendar integration."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from shared.config.runtime_config import load_settings

KST = ZoneInfo("Asia/Seoul")
SCOPES = ("https://www.googleapis.com/auth/calendar.readonly",)
ALLOWED_TRANSPORT_OVERRIDES = {"transit", "driving", "walking"}
@dataclass(frozen=True)
class CalendarEvent:
    """Normalized calendar event for departure calculations."""

    summary: str
    location: str
    start_time: datetime
    event_id: str
    transport_override: str | None = None


def get_upcoming_events() -> list[CalendarEvent]:
    """Return upcoming events with locations inside the configured lookahead window."""
    settings = load_settings()
    lookahead_hours = int(settings.get("schedule", {}).get("lookahead_hours", 0))
    calendar_ids = _parse_calendar_ids(os.environ.get("GOOGLE_CALENDAR_IDS"))
    service = _build_calendar_service()
    now_kst = _current_time_kst()
    window_end = now_kst + timedelta(hours=lookahead_hours)

    seen_event_ids: set[str] = set()
    events: list[CalendarEvent] = []

    for calendar_id in calendar_ids:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=now_kst.isoformat(),
                timeMax=window_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                timeZone="Asia/Seoul",
            )
            .execute()
        )

        for item in response.get("items", []):
            event = _normalize_event(item)
            if event is None:
                continue
            if event.start_time < now_kst or event.start_time > window_end:
                continue
            if event.event_id in seen_event_ids:
                continue
            seen_event_ids.add(event.event_id)
            events.append(event)

    events.sort(key=lambda event: event.start_time)
    return events


def list_upcoming_events() -> list[CalendarEvent]:
    """Backward-compatible alias for older call sites."""
    return get_upcoming_events()


def _build_calendar_service():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise RuntimeError("Google Calendar dependencies are not installed") from exc

    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not service_account_json:
        raise RuntimeError("Missing required environment variable: GOOGLE_SERVICE_ACCOUNT_JSON")

    credentials_info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)

def _parse_calendar_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        raise RuntimeError("Missing required environment variable: GOOGLE_CALENDAR_IDS")

    calendar_ids = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not calendar_ids:
        raise RuntimeError("GOOGLE_CALENDAR_IDS must contain at least one calendar ID")
    return calendar_ids


def _current_time_kst() -> datetime:
    return datetime.now(tz=KST)


def _normalize_event(item: dict[str, Any]) -> CalendarEvent | None:
    location = str(item.get("location", "")).strip()
    if not location:
        return None

    start = item.get("start") or {}
    start_time = _parse_event_start_time(start)
    if start_time is None:
        return None

    summary = str(item.get("summary", "")).strip()
    event_id = str(item.get("id", "")).strip()
    if not event_id:
        return None

    transport_override = _parse_transport_override(item.get("description"))
    return CalendarEvent(
        summary=summary,
        location=location,
        start_time=start_time,
        event_id=event_id,
        transport_override=transport_override,
    )


def _parse_event_start_time(start: dict[str, Any]) -> datetime | None:
    raw_start_time = start.get("dateTime")
    if not raw_start_time:
        return None

    parsed = datetime.fromisoformat(str(raw_start_time).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def _parse_transport_override(description: Any) -> str | None:
    if not description:
        return None

    match = re.search(r"(?im)^\s*transport\s*:\s*([a-z]+)\s*$", str(description))
    if not match:
        return None

    transport = match.group(1).strip().lower()
    if transport not in ALLOWED_TRANSPORT_OVERRIDES:
        return None
    return transport
