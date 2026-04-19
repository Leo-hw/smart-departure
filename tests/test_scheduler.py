from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent
from core.departure_engine import DepartureDecision
from core.scheduler import SchedulePlan, build_daily_plans, get_due_alerts, load_or_build_daily_schedule

KST = ZoneInfo("Asia/Seoul")


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "schedule": {
                "alert_window_minutes": 15,
                "prep_minutes": 60,
            }
        }
        self.now = datetime(2026, 4, 19, 9, 0, tzinfo=KST)

    def test_build_daily_plans_adds_prep_alert_time(self):
        event = CalendarEvent(
            summary="스터디",
            location="강남",
            start_time=datetime(2026, 4, 19, 15, 0, tzinfo=KST),
            event_id="event-1",
            transport_override="transit",
        )
        decision = DepartureDecision(
            event=event,
            transport_mode="transit",
            travel_minutes=35,
            buffer_minutes=10,
            departure_time=datetime(2026, 4, 19, 14, 15, tzinfo=KST),
            should_alert=False,
            is_estimated=False,
            provider="google",
        )

        with patch("core.scheduler.build_departure_decisions", return_value=[decision]):
            plans = build_daily_plans(self.settings, now=self.now, events=[event])

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].prep_alert_time, datetime(2026, 4, 19, 13, 15, tzinfo=KST))

    def test_get_due_alerts_returns_prep_and_departure(self):
        plan = SchedulePlan(
            event_id="event-1",
            summary="스터디",
            location="강남",
            event_start=datetime(2026, 4, 19, 15, 0, tzinfo=KST),
            travel_minutes=35,
            is_estimated=False,
            departure_time=datetime(2026, 4, 19, 14, 15, tzinfo=KST),
            prep_alert_time=datetime(2026, 4, 19, 13, 15, tzinfo=KST),
            transport_mode="transit",
            provider="google",
            buffer_minutes=10,
        )

        prep_due = get_due_alerts([plan], self.settings, now=datetime(2026, 4, 19, 13, 10, tzinfo=KST))
        departure_due = get_due_alerts([plan], self.settings, now=datetime(2026, 4, 19, 14, 20, tzinfo=KST))

        self.assertEqual([item.alert_type for item in prep_due], ["prep"])
        self.assertEqual([item.alert_type for item in departure_due], ["departure"])

    def test_load_or_build_daily_schedule_reuses_today_snapshot(self):
        with tempfile.TemporaryDirectory() as tempdir:
            schedule_path = Path(tempdir) / "schedule_today.json"
            schedule_path.write_text(
                json.dumps(
                    {
                        "date": "2026-04-19",
                        "plans": [
                            {
                                "event_id": "event-1",
                                "summary": "스터디",
                                "location": "강남",
                                "event_start": "2026-04-19T15:00:00+09:00",
                                "travel_minutes": 35,
                                "is_estimated": False,
                                "departure_time": "2026-04-19T14:15:00+09:00",
                                "prep_alert_time": "2026-04-19T13:15:00+09:00",
                                "transport_mode": "transit",
                                "provider": "google",
                                "buffer_minutes": 10,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with patch("core.scheduler.SCHEDULE_TODAY_PATH", schedule_path), patch(
                "core.scheduler.build_daily_plans"
            ) as mock_build:
                plans = load_or_build_daily_schedule(self.settings, now=self.now)

        self.assertEqual(len(plans), 1)
        mock_build.assert_not_called()
