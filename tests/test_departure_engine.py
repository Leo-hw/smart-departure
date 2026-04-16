from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent
from core.maps_service import TravelResult
from core import departure_engine

KST = ZoneInfo("Asia/Seoul")


class DepartureEngineTests(unittest.TestCase):
    def test_build_departure_decisions_uses_default_transport_and_buffer(self):
        event = CalendarEvent(
            summary="Client meeting",
            location="Gangnam",
            start_time=datetime(2026, 4, 16, 15, 0, tzinfo=KST),
            event_id="event-1",
            transport_override=None,
        )
        settings = {
            "user": {
                "home_address": "Seoul Station",
                "default_transport": "transit",
            },
            "transport": {
                "transit": {"buffer_minutes": 10},
            },
            "schedule": {
                "alert_window_minutes": 10,
            },
        }

        with patch.object(departure_engine, "load_settings", return_value=settings), patch.object(
            departure_engine,
            "get_travel_time",
            return_value=TravelResult(duration_minutes=35, is_estimated=False, provider="google"),
        ) as mock_get_travel_time:
            decisions = departure_engine.build_departure_decisions(
                [event],
                now=datetime(2026, 4, 16, 14, 15, tzinfo=KST),
            )

        self.assertEqual(len(decisions), 1)
        decision = decisions[0]
        self.assertEqual(decision.transport_mode, "transit")
        self.assertEqual(decision.travel_minutes, 35)
        self.assertEqual(decision.buffer_minutes, 10)
        self.assertEqual(decision.departure_time, datetime(2026, 4, 16, 14, 15, tzinfo=KST))
        self.assertTrue(decision.should_alert)
        self.assertFalse(decision.is_estimated)
        mock_get_travel_time.assert_called_once_with("Seoul Station", "Gangnam", "transit")

    def test_build_departure_decisions_prefers_transport_override(self):
        event = CalendarEvent(
            summary="Walkable event",
            location="City Hall",
            start_time=datetime(2026, 4, 16, 10, 0, tzinfo=KST),
            event_id="event-2",
            transport_override="walking",
        )
        settings = {
            "user": {
                "home_address": "Home",
                "default_transport": "transit",
            },
            "transport": {
                "transit": {"buffer_minutes": 10},
                "walking": {"buffer_minutes": 5},
            },
            "schedule": {
                "alert_window_minutes": 10,
            },
        }

        with patch.object(departure_engine, "load_settings", return_value=settings), patch.object(
            departure_engine,
            "get_travel_time",
            return_value=TravelResult(duration_minutes=20, is_estimated=True, provider="google"),
        ):
            decisions = departure_engine.build_departure_decisions(
                [event],
                now=datetime(2026, 4, 16, 9, 34, tzinfo=KST),
            )

        decision = decisions[0]
        self.assertEqual(decision.transport_mode, "walking")
        self.assertEqual(decision.buffer_minutes, 5)
        self.assertTrue(decision.should_alert)
        self.assertTrue(decision.is_estimated)

    def test_evaluate_departure_alert_returns_only_alertable_events(self):
        events = [
            CalendarEvent(
                summary="Soon",
                location="Yeoksam",
                start_time=datetime(2026, 4, 16, 12, 0, tzinfo=KST),
                event_id="event-soon",
            ),
            CalendarEvent(
                summary="Later",
                location="Jamsil",
                start_time=datetime(2026, 4, 16, 14, 0, tzinfo=KST),
                event_id="event-later",
            ),
        ]
        decisions = [
            departure_engine.DepartureDecision(
                event=events[0],
                transport_mode="transit",
                travel_minutes=40,
                buffer_minutes=10,
                departure_time=datetime(2026, 4, 16, 11, 10, tzinfo=KST),
                should_alert=True,
                is_estimated=False,
                provider="google",
            ),
            departure_engine.DepartureDecision(
                event=events[1],
                transport_mode="transit",
                travel_minutes=30,
                buffer_minutes=10,
                departure_time=datetime(2026, 4, 16, 13, 20, tzinfo=KST),
                should_alert=False,
                is_estimated=False,
                provider="google",
            ),
        ]

        with patch.object(departure_engine, "build_departure_decisions", return_value=decisions) as mock_build:
            alertable = departure_engine.evaluate_departure_alert(
                events,
                now=datetime(2026, 4, 16, 11, 10, tzinfo=KST),
            )

        self.assertEqual([item.event.event_id for item in alertable], ["event-soon"])
        mock_build.assert_called_once()

    def test_evaluate_departure_alert_fetches_events_when_none_provided(self):
        event = CalendarEvent(
            summary="Fetched",
            location="Hongdae",
            start_time=datetime(2026, 4, 16, 18, 0, tzinfo=KST),
            event_id="event-fetched",
        )
        decision = departure_engine.DepartureDecision(
            event=event,
            transport_mode="transit",
            travel_minutes=25,
            buffer_minutes=10,
            departure_time=datetime(2026, 4, 16, 17, 25, tzinfo=KST),
            should_alert=True,
            is_estimated=False,
            provider="google",
        )

        with patch.object(departure_engine, "get_upcoming_events", return_value=[event]) as mock_events, patch.object(
            departure_engine, "build_departure_decisions", return_value=[decision]
        ) as mock_build:
            alertable = departure_engine.evaluate_departure_alert()

        self.assertEqual(len(alertable), 1)
        self.assertEqual(alertable[0].event.event_id, "event-fetched")
        mock_events.assert_called_once_with()
        mock_build.assert_called_once_with([event], now=None)

    def test_build_departure_decisions_raises_when_home_address_missing(self):
        event = CalendarEvent(
            summary="Broken setup",
            location="Mapo",
            start_time=datetime(2026, 4, 16, 18, 0, tzinfo=KST),
            event_id="event-3",
        )
        settings = {
            "user": {
                "home_address": "",
                "default_transport": "transit",
            },
            "transport": {},
            "schedule": {"alert_window_minutes": 10},
        }

        with patch.object(departure_engine, "load_settings", return_value=settings):
            with self.assertRaisesRegex(RuntimeError, "HOME_ADDRESS is required"):
                departure_engine.build_departure_decisions([event])


if __name__ == "__main__":
    unittest.main()
