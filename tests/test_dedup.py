from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent
from core.dedup import (
    filter_pending_decisions,
    mark_skipped_deliveries,
    mark_successful_deliveries,
)
from core.departure_engine import DepartureDecision
from core.privacy import short_id
from core.scheduler import SchedulePlan, ScheduledAlert, select_latest_prep_alerts

KST = ZoneInfo("Asia/Seoul")


class DedupTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.sent_alerts_path = Path(self.tempdir.name) / "sent_alerts.json"
        self.settings = {"schedule": {"dedup_ttl_minutes": 60}}
        self.now = datetime(2026, 4, 16, 14, 15, tzinfo=KST)
        self.decision = DepartureDecision(
            event=CalendarEvent(
                summary="스터디 모임",
                location="강남구 역삼동 OO카페",
                start_time=datetime(2026, 4, 16, 15, 0, tzinfo=KST),
                event_id="event-1",
                transport_override="transit",
            ),
            transport_mode="transit",
            travel_minutes=35,
            buffer_minutes=10,
            departure_time=datetime(2026, 4, 16, 14, 15, tzinfo=KST),
            should_alert=True,
            is_estimated=False,
            provider="google",
        )

    def test_filter_pending_decisions_skips_recently_sent_event(self):
        self.sent_alerts_path.parent.mkdir(parents=True, exist_ok=True)
        self.sent_alerts_path.write_text(
            json.dumps(
                {
                    short_id("event-1"): {
                        "status": "sent",
                        "sent_at": (self.now - timedelta(minutes=15)).isoformat(),
                        "event_start": self.decision.event.start_time.isoformat(),
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            pending, skipped = filter_pending_decisions([self.decision], self.settings, now=self.now)

        self.assertEqual(len(pending), 0)
        self.assertEqual([item.event.event_id for item in skipped], ["event-1"])

    def test_filter_pending_decisions_prunes_after_event_start_plus_60_minutes(self):
        after_expiry = self.decision.event.start_time + timedelta(minutes=61)
        self.sent_alerts_path.parent.mkdir(parents=True, exist_ok=True)
        self.sent_alerts_path.write_text(
            json.dumps(
                {
                    short_id("event-1"): {
                        "status": "sent",
                        "sent_at": self.now.isoformat(),
                        "event_start": self.decision.event.start_time.isoformat(),
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            pending, skipped = filter_pending_decisions(
                [self.decision],
                self.settings,
                now=after_expiry,
            )

        self.assertEqual([item.event.event_id for item in pending], ["event-1"])
        self.assertEqual(len(skipped), 0)
        persisted = json.loads(self.sent_alerts_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted, {})

    def test_mark_successful_deliveries_persists_sent_alert(self):
        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            mark_successful_deliveries([self.decision], self.settings, now=self.now)

        persisted = json.loads(self.sent_alerts_path.read_text(encoding="utf-8"))
        hashed_key = short_id("event-1")
        self.assertIn(hashed_key, persisted)
        self.assertEqual(persisted[hashed_key]["sent_at"], self.now.isoformat())
        self.assertEqual(persisted[hashed_key]["status"], "sent")
        self.assertEqual(
            persisted[hashed_key]["event_start"],
            self.decision.event.start_time.isoformat(),
        )
        serialized = json.dumps(persisted, ensure_ascii=False)
        self.assertNotIn("event-1", serialized)
        self.assertNotIn("스터디 모임", serialized)
        self.assertNotIn("강남구 역삼동 OO카페", serialized)

    def test_mark_skipped_deliveries_persists_skipped_status(self):
        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            mark_skipped_deliveries([self.decision], self.settings, now=self.now)

        persisted = json.loads(self.sent_alerts_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted[short_id("event-1")]["status"], "skipped")

    def test_legacy_plaintext_key_is_migrated_to_hash(self):
        self.sent_alerts_path.parent.mkdir(parents=True, exist_ok=True)
        self.sent_alerts_path.write_text(
            json.dumps(
                {
                    "event-1": {
                        "event_id": "event-1",
                        "summary": "스터디 모임",
                        "location": "강남구 역삼동 OO카페",
                        "status": "sent",
                        "sent_at": self.now.isoformat(),
                        "event_start": self.decision.event.start_time.isoformat(),
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            pending, skipped = filter_pending_decisions(
                [self.decision],
                self.settings,
                now=self.now,
            )

        persisted = json.loads(self.sent_alerts_path.read_text(encoding="utf-8"))
        self.assertEqual(pending, [])
        self.assertEqual(skipped, [self.decision])
        self.assertEqual(list(persisted), [short_id("event-1")])
        serialized = json.dumps(persisted, ensure_ascii=False)
        self.assertNotIn("event-1", serialized)
        self.assertNotIn("스터디 모임", serialized)
        self.assertNotIn("강남구 역삼동 OO카페", serialized)

    def test_older_missed_prep_is_persisted_as_skipped(self):
        plan = SchedulePlan(
            event_id="event-1",
            summary="스터디 모임",
            location="강남",
            event_start=datetime(2026, 4, 16, 15, 0, tzinfo=KST),
            travel_minutes=35,
            is_estimated=False,
            departure_time=datetime(2026, 4, 16, 14, 15, tzinfo=KST),
            prep_alert_time=datetime(2026, 4, 16, 13, 15, tzinfo=KST),
            transport_mode="transit",
            provider="google",
            buffer_minutes=10,
        )
        older = ScheduledAlert(
            "prep",
            datetime(2026, 4, 16, 12, 45, tzinfo=KST),
            plan,
            classification="catch_up",
            evaluated_at=self.now,
        )
        latest = ScheduledAlert(
            "prep",
            datetime(2026, 4, 16, 13, 45, tzinfo=KST),
            plan,
            classification="catch_up",
            evaluated_at=self.now,
        )

        selected, sealed = select_latest_prep_alerts([older, latest], now=self.now)
        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            mark_skipped_deliveries(sealed, self.settings, now=self.now)

        persisted = json.loads(self.sent_alerts_path.read_text(encoding="utf-8"))
        self.assertEqual([item.dedup_key for item in selected], [latest.dedup_key])
        hashed_key = short_id(older.dedup_key)
        self.assertEqual(persisted[hashed_key]["status"], "skipped")
        self.assertEqual(
            persisted[hashed_key]["event_start"],
            plan.event_start.isoformat(),
        )


if __name__ == "__main__":
    unittest.main()
