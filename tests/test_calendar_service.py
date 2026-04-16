from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from core import calendar_service


class _FakeRequest:
    def __init__(self, payload: dict):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeEventsResource:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[dict] = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeRequest(self.responses.get(kwargs["calendarId"], {"items": []}))


class _FakeService:
    def __init__(self, responses: dict[str, dict]):
        self._events = _FakeEventsResource(responses)

    def events(self):
        return self._events


class CalendarServiceTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "user": {"home_address": "서울시 OO구 OO동 OO"},
            "schedule": {"lookahead_hours": 3},
        }

    def test_get_upcoming_events_filters_and_normalizes_events(self):
        original_env = {
            "GOOGLE_SERVICE_ACCOUNT_JSON": calendar_service.os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"),
            "GOOGLE_CALENDAR_IDS": calendar_service.os.environ.get("GOOGLE_CALENDAR_IDS"),
        }
        self.addCleanup(self._restore_env, original_env)
        calendar_service.os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = '{"type": "service_account"}'
        calendar_service.os.environ["GOOGLE_CALENDAR_IDS"] = "calendar-a, calendar-b"

        original_now = calendar_service._current_time_kst
        calendar_service._current_time_kst = lambda: datetime(2026, 4, 15, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        self.addCleanup(self._restore_now, original_now)

        fake_service = _FakeService(
            {
                "calendar-a": {
                    "items": [
                        {
                            "id": "event-1",
                            "summary": "Morning standup",
                            "location": "Gangnam",
                            "start": {"dateTime": "2026-04-15T00:30:00Z"},
                            "description": "transport: driving\nbring laptop",
                        },
                        {
                            "id": "event-empty-location",
                            "summary": "Hidden event",
                            "location": "  ",
                            "start": {"dateTime": "2026-04-15T01:00:00Z"},
                        },
                        {
                            "id": "event-outside-window",
                            "summary": "Too late",
                            "location": "Yeoksam",
                            "start": {"dateTime": "2026-04-15T03:30:00Z"},
                        },
                        {
                            "id": "event-all-day",
                            "summary": "All day event",
                            "location": "Seoul",
                            "start": {"date": "2026-04-15"},
                        },
                    ]
                },
                "calendar-b": {
                    "items": [
                        {
                            "id": "event-1",
                            "summary": "Morning standup duplicate",
                            "location": "Gangnam",
                            "start": {"dateTime": "2026-04-15T00:30:00Z"},
                            "description": "transport: transit",
                        },
                        {
                            "id": "event-2",
                            "summary": "Lunch",
                            "location": "City Hall",
                            "start": {"dateTime": "2026-04-15T01:15:00Z"},
                            "description": "transport: bicycle",
                        },
                    ]
                },
            }
        )
        original_builder = calendar_service._build_calendar_service
        calendar_service._build_calendar_service = lambda: fake_service
        self.addCleanup(self._restore_builder, original_builder)
        original_load_settings = calendar_service.load_settings
        calendar_service.load_settings = lambda: self.settings
        self.addCleanup(self._restore_load_settings, original_load_settings)

        events = calendar_service.get_upcoming_events()

        self.assertEqual([event.event_id for event in events], ["event-1", "event-2"])
        self.assertEqual(events[0].summary, "Morning standup")
        self.assertEqual(events[0].location, "Gangnam")
        self.assertEqual(events[0].start_time, datetime(2026, 4, 15, 9, 30, tzinfo=ZoneInfo("Asia/Seoul")))
        self.assertEqual(events[0].transport_override, "driving")
        self.assertEqual(events[1].start_time, datetime(2026, 4, 15, 10, 15, tzinfo=ZoneInfo("Asia/Seoul")))
        self.assertIsNone(events[1].transport_override)
        self.assertEqual(events[0].start_time.tzinfo.key, "Asia/Seoul")

        calls = fake_service.events().calls
        self.assertEqual([call["calendarId"] for call in calls], ["calendar-a", "calendar-b"])
        self.assertTrue(all(call["singleEvents"] is True for call in calls))
        self.assertTrue(all(call["orderBy"] == "startTime" for call in calls))
        self.assertTrue(all(call["timeZone"] == "Asia/Seoul" for call in calls))

    def test_transport_override_helper_accepts_only_allowed_values(self):
        self.assertEqual(calendar_service._parse_transport_override("transport: transit"), "transit")
        self.assertEqual(calendar_service._parse_transport_override("transport: driving"), "driving")
        self.assertEqual(calendar_service._parse_transport_override("transport: walking"), "walking")
        self.assertIsNone(calendar_service._parse_transport_override("transport: bicycle"))
        self.assertIsNone(calendar_service._parse_transport_override("other: transit"))

    def _restore_env(self, original_env):
        for key, value in original_env.items():
            if value is None:
                calendar_service.os.environ.pop(key, None)
            else:
                calendar_service.os.environ[key] = value

    def _restore_now(self, original_now):
        calendar_service._current_time_kst = original_now

    def _restore_builder(self, original_builder):
        calendar_service._build_calendar_service = original_builder

    def _restore_load_settings(self, original_load_settings):
        calendar_service.load_settings = original_load_settings


if __name__ == "__main__":
    unittest.main()
