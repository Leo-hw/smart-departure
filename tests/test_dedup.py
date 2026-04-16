from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent
from core.dedup import filter_pending_decisions, mark_successful_deliveries
from core.departure_engine import DepartureDecision

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
                    "event-1": {
                        "sent_at": (self.now - timedelta(minutes=15)).isoformat(),
                        "departure_time": self.decision.departure_time.isoformat(),
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            pending, skipped = filter_pending_decisions([self.decision], self.settings, now=self.now)

        self.assertEqual(len(pending), 0)
        self.assertEqual([item.event.event_id for item in skipped], ["event-1"])

    def test_filter_pending_decisions_prunes_expired_record(self):
        self.sent_alerts_path.parent.mkdir(parents=True, exist_ok=True)
        self.sent_alerts_path.write_text(
            json.dumps(
                {
                    "event-1": {
                        "sent_at": (self.now - timedelta(hours=2)).isoformat(),
                        "departure_time": self.decision.departure_time.isoformat(),
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            pending, skipped = filter_pending_decisions([self.decision], self.settings, now=self.now)

        self.assertEqual([item.event.event_id for item in pending], ["event-1"])
        self.assertEqual(len(skipped), 0)
        persisted = json.loads(self.sent_alerts_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted, {})

    def test_mark_successful_deliveries_persists_sent_alert(self):
        with patch("core.dedup.SENT_ALERTS_PATH", self.sent_alerts_path):
            mark_successful_deliveries([self.decision], self.settings, now=self.now)

        persisted = json.loads(self.sent_alerts_path.read_text(encoding="utf-8"))
        self.assertIn("event-1", persisted)
        self.assertEqual(persisted["event-1"]["sent_at"], self.now.isoformat())


if __name__ == "__main__":
    unittest.main()
