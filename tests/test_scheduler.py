from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent
from core.dedup import filter_pending_decisions
from core.departure_engine import DepartureDecision
from core.privacy import short_id
from core.scheduler import (
    PrepStage,
    SchedulePlan,
    ScheduledAlert,
    build_daily_plans,
    classify_occasion,
    get_alert_candidates,
    classify_alert,
    get_due_alerts,
    load_or_build_daily_schedule,
    select_latest_prep_alerts,
)
from shared.config.runtime_config import load_settings

KST = ZoneInfo("Asia/Seoul")


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "schedule": {
                "alert_window_minutes": 15,
            }
        }
        self.settings["prep_profiles"] = load_settings()["prep_profiles"]
        self.now = datetime(2026, 4, 19, 9, 0, tzinfo=KST)

    def test_build_daily_plans_adds_casual_stages(self):
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
        self.assertEqual(plans[0].occasion, "casual")
        self.assertEqual(plans[0].stages, (PrepStage("준비 시작", datetime(2026, 4, 19, 13, 15, tzinfo=KST)),))

    def test_occasion_priority_and_override(self):
        event = CalendarEvent("면접 후 데이트", "강남", self.now, "event-1")
        self.assertEqual(classify_occasion(event, self.settings), "formal")
        overridden = CalendarEvent("면접", "강남", self.now, "event-2", occasion_override="sports")
        self.assertEqual(classify_occasion(overridden, self.settings), "sports")
        unknown = CalendarEvent("일상", "강남", self.now, "event-3", occasion_override="unknown")
        self.assertEqual(classify_occasion(unknown, self.settings), "casual")

    def test_formal_stages_have_independent_stable_keys(self):
        plan = self._make_plan()
        plan = SchedulePlan(**{**vars(plan), "occasion": "formal", "prep_alert_time": None,
            "stages": (
                PrepStage("샤워 & 준비 시작", plan.departure_time - timedelta(minutes=120)),
                PrepStage("옷 입기 (정장)", plan.departure_time - timedelta(minutes=45)),
            )})
        first = get_alert_candidates([plan], self.settings, now=plan.departure_time - timedelta(minutes=120))
        second = get_alert_candidates([plan], self.settings, now=plan.departure_time - timedelta(minutes=45))
        self.assertEqual(first[0].stage_label, "샤워 & 준비 시작")
        self.assertEqual(second[-1].stage_label, "옷 입기 (정장)")
        self.assertNotEqual(first[0].dedup_key, second[-1].dedup_key)
        moved = SchedulePlan(**{**vars(plan), "departure_time": plan.departure_time - timedelta(minutes=5)})
        moved_alert = get_alert_candidates([moved], self.settings, now=plan.departure_time - timedelta(minutes=120))[0]
        self.assertEqual(first[0].dedup_key, moved_alert.dedup_key)

    def test_stage_profile_offsets(self):
        expected = {
            "formal": [120, 45], "semi_formal": [90, 30],
            "casual": [60], "travel": [180, 30], "sports": [30],
        }
        from core.scheduler import _build_stages
        departure = datetime(2026, 4, 19, 14, 15, tzinfo=KST)
        for occasion, offsets in expected.items():
            with self.subTest(occasion=occasion):
                stages = _build_stages(occasion, departure, self.settings)
                self.assertEqual(
                    [(departure - stage.alert_time) // timedelta(minutes=1) for stage in stages],
                    sorted(offsets, reverse=True),
                )

    def test_newer_early_window_prep_seals_older_catch_up(self):
        plan = self._make_plan()
        now = datetime(2026, 4, 19, 13, 20, tzinfo=KST)
        old = ScheduledAlert("prep", datetime(2026, 4, 19, 12, 15, tzinfo=KST), plan)
        new = ScheduledAlert("prep", datetime(2026, 4, 19, 13, 30, tzinfo=KST), plan)
        selected, sealed = select_latest_prep_alerts([old, new], now=now)
        self.assertEqual(selected, [new])
        self.assertEqual(sealed, [old])

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

    def test_departure_catch_up_uses_default_45_minutes(self):
        plan = self._make_plan()
        departure = ScheduledAlert("departure", plan.departure_time, plan)

        self.assertEqual(
            classify_alert(
                departure,
                plan.departure_time + timedelta(minutes=40),
                self.settings,
            ),
            "catch_up",
        )
        self.assertEqual(
            classify_alert(
                departure,
                plan.departure_time + timedelta(minutes=46),
                self.settings,
            ),
            "expired",
        )

    def test_departure_catch_up_respects_configured_minutes(self):
        plan = self._make_plan()
        departure = ScheduledAlert("departure", plan.departure_time, plan)
        settings = {
            "schedule": {
                **self.settings["schedule"],
                "departure_catchup_minutes": 60,
            }
        }

        self.assertEqual(
            classify_alert(
                departure,
                plan.departure_time + timedelta(minutes=50),
                settings,
            ),
            "catch_up",
        )

    def test_prep_catch_up_still_expires_at_departure_time(self):
        plan = self._make_plan()
        prep = ScheduledAlert("prep", plan.prep_alert_time, plan)
        settings = {
            "schedule": {
                **self.settings["schedule"],
                "departure_catchup_minutes": 90,
            }
        }

        self.assertEqual(
            classify_alert(prep, plan.departure_time, settings),
            "catch_up",
        )
        self.assertEqual(
            classify_alert(
                prep,
                plan.departure_time + timedelta(minutes=1),
                settings,
            ),
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

    def test_load_or_build_daily_schedule_rebuilds_today_snapshot_by_default(self):
        with tempfile.TemporaryDirectory() as tempdir:
            schedule_path = Path(tempdir) / "schedule_today.json"
            schedule_path.write_text(
                json.dumps(
                    {
                        "date": "2026-04-19",
                        "built_at": "2026-04-19T08:55:00+09:00",
                        "plans": [],
                    }
                ),
                encoding="utf-8",
            )
            new_plan = self._make_plan()

            with patch("core.scheduler.SCHEDULE_TODAY_PATH", schedule_path), patch(
                "core.scheduler.build_daily_plans",
                return_value=[new_plan],
            ) as mock_build:
                plans = load_or_build_daily_schedule(self.settings, now=self.now)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].event_id, "event-1")
        mock_build.assert_called_once_with(self.settings, now=self.now)

    def test_load_or_build_daily_schedule_reuses_fresh_snapshot_when_ttl_enabled(self):
        settings = {
            **self.settings,
            "schedule": {
                **self.settings["schedule"],
                "snapshot_ttl_minutes": 10,
            },
        }
        with tempfile.TemporaryDirectory() as tempdir:
            schedule_path = Path(tempdir) / "schedule_today.json"
            schedule_path.write_text(
                json.dumps(
                    {
                        "date": self.now.date().isoformat(),
                        "version": 2,
                        "built_at": (self.now - timedelta(minutes=5)).isoformat(),
                        "plans": [self._serialized_plan()],
                    }
                ),
                encoding="utf-8",
            )

            with patch("core.scheduler.SCHEDULE_TODAY_PATH", schedule_path), patch(
                "core.scheduler.build_daily_plans"
            ) as mock_build:
                plans = load_or_build_daily_schedule(settings, now=self.now)

        self.assertEqual([plan.event_id for plan in plans], ["event-1"])
        mock_build.assert_not_called()

    def test_stage_snapshot_round_trip_keeps_alert_keys(self):
        plan = self._make_plan()
        stage = PrepStage("준비 시작", plan.departure_time - timedelta(minutes=60))
        plan = SchedulePlan(**{**vars(plan), "prep_alert_time": None, "stages": (stage,)})
        with tempfile.TemporaryDirectory() as tempdir:
            schedule_path = Path(tempdir) / "schedule_today.json"
            with patch("core.scheduler.SCHEDULE_TODAY_PATH", schedule_path), patch(
                "core.scheduler.build_daily_plans", return_value=[plan]
            ):
                load_or_build_daily_schedule(self.settings, now=self.now)
            snapshot = json.loads(schedule_path.read_text(encoding="utf-8"))
            cached_settings = {**self.settings, "schedule": {**self.settings["schedule"], "snapshot_ttl_minutes": 10}}
            with patch("core.scheduler.SCHEDULE_TODAY_PATH", schedule_path), patch(
                "core.scheduler.build_daily_plans"
            ) as mock_build:
                restored = load_or_build_daily_schedule(cached_settings, now=self.now + timedelta(minutes=5))
        self.assertEqual(restored[0].stages, (stage,))
        self.assertEqual(
            snapshot["plans"][0]["stages"][0]["alert_key"],
            ScheduledAlert("prep", stage.alert_time, plan, stage_id=stage.stage_id).dedup_key,
        )
        mock_build.assert_not_called()

    def test_schedule_rebuild_does_not_modify_dedup_state(self):
        with tempfile.TemporaryDirectory() as tempdir:
            schedule_path = Path(tempdir) / "schedule_today.json"
            sent_alerts_path = Path(tempdir) / "sent_alerts.json"
            plan = self._make_plan()
            departure_alert = ScheduledAlert(
                alert_type="departure",
                alert_time=plan.departure_time,
                plan=plan,
            )
            original_dedup = {
                departure_alert.dedup_key: {
                    "status": "sent",
                    "sent_at": "2026-04-19T14:15:00+09:00",
                    "event_start": plan.event_start.isoformat(),
                }
            }
            sent_alerts_path.write_text(
                json.dumps(original_dedup),
                encoding="utf-8",
            )

            with patch("core.scheduler.SCHEDULE_TODAY_PATH", schedule_path), patch(
                "core.scheduler.build_daily_plans",
                return_value=[plan],
            ), patch("core.dedup.SENT_ALERTS_PATH", sent_alerts_path):
                load_or_build_daily_schedule(self.settings, now=self.now)
                pending, skipped = filter_pending_decisions(
                    [departure_alert],
                    self.settings,
                    now=plan.departure_time,
                )

            persisted_dedup = json.loads(sent_alerts_path.read_text(encoding="utf-8"))
            snapshot = json.loads(schedule_path.read_text(encoding="utf-8"))

        self.assertEqual(
            persisted_dedup,
            {short_id(departure_alert.dedup_key): original_dedup[departure_alert.dedup_key]},
        )
        self.assertEqual(snapshot["built_at"], self.now.isoformat())
        self.assertEqual(snapshot["version"], 2)
        self.assertEqual(snapshot["plans"][0]["stages"][-1]["label"], "출발")
        self.assertEqual(snapshot["plans"][0]["stages"][-1]["alert_key"], departure_alert.dedup_key)
        self.assertNotIn("prep_alert_time", snapshot["plans"][0])
        self.assertEqual(pending, [])
        self.assertEqual(skipped, [departure_alert])

    def _serialized_plan(self):
        return {
            "event_id": "event-1",
            "summary": "스터디",
            "location": "강남",
            "event_start": "2026-04-19T15:00:00+09:00",
            "travel_minutes": 35,
            "is_estimated": False,
            "departure_time": "2026-04-19T14:15:00+09:00",
            "occasion": "casual",
            "stages": [{"label": "준비 시작", "alert_time": "2026-04-19T13:15:00+09:00", "alert_key": "event-1:2026-04-19T15:00:00+09:00:prep:준비 시작"}, {"label": "출발", "alert_time": "2026-04-19T14:15:00+09:00", "alert_key": "event-1:2026-04-19T15:00:00+09:00:departure"}],
            "transport_mode": "transit",
            "provider": "google",
            "buffer_minutes": 10,
        }
