from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from googleapiclient.errors import HttpError
from httplib2 import Response

from core import calendar_service


class _FakeRequest:
    def __init__(self, payload: dict):
        self._payload = payload
        self.num_retries = None

    def execute(self, num_retries=0):
        self.num_retries = num_retries
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeEventsResource:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[dict] = []
        self.requests: list[_FakeRequest] = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        request = _FakeRequest(self.responses.get(kwargs["calendarId"], {"items": []}))
        self.requests.append(request)
        return request


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
                            "description": "transport: driving\noccasion: formal\nbring laptop",
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
        self.assertEqual(events[0].occasion_override, "formal")
        self.assertEqual(events[1].start_time, datetime(2026, 4, 15, 10, 15, tzinfo=ZoneInfo("Asia/Seoul")))
        self.assertIsNone(events[1].transport_override)
        self.assertEqual(events[0].start_time.tzinfo.key, "Asia/Seoul")

        calls = fake_service.events().calls
        self.assertEqual([call["calendarId"] for call in calls], ["calendar-a", "calendar-b"])
        self.assertTrue(all(call["singleEvents"] is True for call in calls))
        self.assertTrue(all(call["orderBy"] == "startTime" for call in calls))
        self.assertTrue(all(call["timeZone"] == "Asia/Seoul" for call in calls))
        self.assertTrue(
            all(
                request.num_retries == calendar_service.CALENDAR_API_RETRIES
                for request in fake_service.events().requests
            )
        )

    def test_calendar_request_retries_transient_failures_then_succeeds(self):
        class RetryRequest:
            def __init__(self):
                self.attempts = 0
                self.num_retries = None

            def execute(self, num_retries=0):
                self.num_retries = num_retries
                while True:
                    self.attempts += 1
                    if self.attempts <= 2 and self.attempts <= num_retries:
                        continue
                    if self.attempts <= 2:
                        raise TimeoutError("temporary timeout")
                    return {
                        "items": [
                            {
                                "id": "event-retried",
                                "summary": "Retried event",
                                "location": "Gangnam",
                                "start": {"dateTime": "2026-04-15T00:30:00Z"},
                            }
                        ]
                    }

        request = RetryRequest()

        class RetryEvents:
            def list(self, **kwargs):
                return request

        class RetryService:
            def events(self):
                return RetryEvents()

        with patch.dict(
            calendar_service.os.environ,
            {
                "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type": "service_account"}',
                "GOOGLE_CALENDAR_IDS": "calendar-a",
            },
        ), patch.object(
            calendar_service,
            "_current_time_kst",
            return_value=datetime(2026, 4, 15, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        ), patch.object(
            calendar_service,
            "_build_calendar_service",
            return_value=RetryService(),
        ), patch.object(
            calendar_service,
            "load_settings",
            return_value=self.settings,
        ):
            events = calendar_service.get_upcoming_events()

        self.assertEqual([event.event_id for event in events], ["event-retried"])
        self.assertEqual(request.num_retries, 3)
        self.assertEqual(request.attempts, 3)

    def test_transport_override_helper_accepts_only_allowed_values(self):
        self.assertEqual(calendar_service._parse_transport_override("transport: transit"), "transit")
        self.assertEqual(calendar_service._parse_transport_override("transport: driving"), "driving")
        self.assertEqual(calendar_service._parse_transport_override("transport: walking"), "walking")
        self.assertIsNone(calendar_service._parse_transport_override("transport: bicycle"))
        self.assertIsNone(calendar_service._parse_transport_override("other: transit"))

    def test_unavailable_calendar_does_not_block_healthy_calendar(self):
        secret_id = "private-calendar-id@example.com"
        secret_response = "private-address-and-credential"
        failure = self._http_error(404, "notFound", secret_response)
        service = _FakeService({
            secret_id: failure,
            "healthy-calendar": {"items": [{
                "id": "event-1", "summary": "meeting", "location": "Seoul",
                "start": {"dateTime": "2026-04-15T00:30:00Z"},
            }]},
        })
        stderr = io.StringIO()
        with self._calendar_context(f"{secret_id},healthy-calendar", service), redirect_stderr(stderr):
            events = calendar_service.get_upcoming_events()

        self.assertEqual([event.event_id for event in events], ["event-1"])
        self.assertIn("slot=1 status=404", stderr.getvalue())
        self.assertNotIn(secret_id, stderr.getvalue())
        self.assertNotIn(secret_response, stderr.getvalue())
        self.assertNotIn("meeting", stderr.getvalue())
        self.assertEqual(len(service.events().calls), 2)

    def test_403_permission_denied_skips_only_one_calendar(self):
        service = _FakeService({
            "blocked": self._http_error(403, "forbidden"),
            "empty-but-accessible": {"items": []},
        })
        with self._calendar_context("blocked,empty-but-accessible", service), redirect_stderr(io.StringIO()):
            self.assertEqual(calendar_service.get_upcoming_events(), [])

    def test_all_calendars_unavailable_is_failure(self):
        service = _FakeService({
            "first": self._http_error(404, "notFound"),
            "second": self._http_error(403, "forbidden"),
        })
        with self._calendar_context("first,second", service), redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "All configured calendars are unavailable"):
                calendar_service.get_upcoming_events()

    def test_global_http_and_network_failures_are_not_swallowed(self):
        for failure in (
            self._http_error(401, "authError"),
            self._http_error(403, "quotaExceeded"),
            self._http_error(403, "insufficientPermissions"),
            self._http_error(429, "rateLimitExceeded"),
            self._http_error(500, "backendError"),
            OSError("network unavailable"),
        ):
            with self.subTest(failure=type(failure).__name__, status=getattr(getattr(failure, "resp", None), "status", None)):
                service = _FakeService({"failed": failure, "next": {"items": []}})
                with self._calendar_context("failed,next", service):
                    with self.assertRaises(type(failure)):
                        calendar_service.get_upcoming_events()
                self.assertEqual(len(service.events().calls), 1)

    def _calendar_context(self, calendar_ids, service):
        from contextlib import ExitStack
        stack = ExitStack()
        stack.enter_context(patch.dict(calendar_service.os.environ, {"GOOGLE_CALENDAR_IDS": calendar_ids}))
        stack.enter_context(patch.object(calendar_service, "load_settings", return_value=self.settings))
        stack.enter_context(patch.object(calendar_service, "_build_calendar_service", return_value=service))
        stack.enter_context(patch.object(
            calendar_service, "_current_time_kst",
            return_value=datetime(2026, 4, 15, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        ))
        return stack

    def _http_error(self, status, reason, message="failure"):
        content = json.dumps({"error": {"errors": [{"reason": reason}], "message": message}}).encode()
        return HttpError(Response({"status": status}), content)

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
