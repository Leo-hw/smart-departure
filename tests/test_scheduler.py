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
from core.scheduler import (
    SchedulePlan,
    ScheduledAlert,
    build_daily_plans,
    classify_alert,
    get_due_alerts,
    load_or_build_daily_schedule,
    select_latest_prep_alerts,
)

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
        plan = self._make_plan()

        prep_due = get_due_alerts([plan], self.settings, now=datetime(2026, 4, 19, 13, 10, tzinfo=KST))
        departure_due = get_due_alerts([plan], self.settings, now=datetime(2026, 4, 19, 14, 20, tzinfo=KST))

        self.assertEqual([item.alert_type for item in prep_due], ["prep"])
        self.assertEqual([item.alert_type for item in departure_due], ["departure"])

    def test_classify_alert_on_time_catch_up_and_expired(self):
        plan = self._make_plan()
        prep = ScheduledAlert("prep", plan.prep_alert_time, plan)

        self.assertEqual(
            classify_alert(prep, datetime(2026, 4, 19, 13, 10, tzinfo=KST), self.settings),
            "on_time",
        )
        self.assertEqual(
            classify_alert(prep, datetime(2026, 4, 19, 13, 40, tzinfo=KST), self.settings),
            "catch_up",
        )
        self.assertEqual(
            classify_alert(prep, datetime(2026, 4, 19, 14, 16, tzinfo=KST), self.settings),
            "expired",
        )

    def test_select_latest_prep_alert_seals_older_stages(self):
        plan = self._make_plan()
        now = datetime(2026, 4, 19, 13, 50, tzinfo=KST)
        alerts = [
            ScheduledAlert(
                "prep",
                datetime(2026, 4, 19, 12, 45, tzinfo=KST),
                plan,
                classification="catch_up",
                evaluated_at=now,
            ),
            ScheduledAlert(
                "prep",
                datetime(2026, 4, 19, 13, 30, tzinfo=KST),
                plan,
                classification="catch_up",
                evaluated_at=now,
            ),
        ]

        selected, sealed = select_latest_prep_alerts(alerts, now=now)

        self.assertEqual([item.alert_time for item in selected], [alerts[1].alert_time])
        self.assertEqual([item.alert_time for item in sealed], [alerts[0].alert_time])

    def _make_plan(self):
        return SchedulePlan(
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
