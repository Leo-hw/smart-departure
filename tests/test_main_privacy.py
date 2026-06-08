from __future__ import annotations

import io
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

import main
from core.notifier import NotificationDelivery
from core.privacy import short_id
from core.scheduler import SchedulePlan, ScheduledAlert

KST = ZoneInfo("Asia/Seoul")


class MainPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.plan = SchedulePlan(
            event_id="private-event-id",
            summary="민감한 병원 일정",
            location="서울시 민감구 비밀로 123",
            event_start=datetime(2026, 6, 8, 18, 0, tzinfo=KST),
            travel_minutes=30,
            is_estimated=False,
            departure_time=datetime(2026, 6, 8, 17, 20, tzinfo=KST),
            prep_alert_time=datetime(2026, 6, 8, 16, 20, tzinfo=KST),
            transport_mode="transit",
            provider="google",
            buffer_minutes=10,
        )
        self.alert = ScheduledAlert(
            alert_type="departure",
            alert_time=self.plan.departure_time,
            plan=self.plan,
        )
        self.settings = {
            "user": {"default_transport": "transit"},
            "notification": {"enabled_channels": ["discord"]},
        }

    def test_success_logs_exclude_event_details_and_plaintext_id(self):
        delivery = NotificationDelivery(
            channel="discord",
            event_id=self.plan.event_id,
            success=False,
            error="Discord returned status 403",
            dedup_key=self.alert.dedup_key,
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(main, "load_dotenv_file"), patch.object(
            main, "load_settings", return_value=self.settings
        ), patch.object(
            main,
            "validate_environment",
            return_value={"GOOGLE_CALENDAR_IDS": "calendar-a"},
        ), patch.object(main, "ensure_runtime_dir"), patch.object(
            main, "load_or_build_daily_schedule", return_value=[self.plan]
        ), patch.object(
            main, "get_alert_candidates", return_value=[self.alert]
        ), patch.object(
            main,
            "filter_pending_decisions",
            return_value=([self.alert], []),
        ), patch.object(
            main,
            "select_latest_prep_alerts",
            return_value=([self.alert], []),
        ), patch.object(
            main, "send_notifications", return_value=[delivery]
        ), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main.main()

        output = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(result, 1)
        self.assertIn(short_id(self.plan.event_id), output)
        self.assertNotIn(self.plan.event_id, output)
        self.assertNotIn(self.plan.summary, output)
        self.assertNotIn(self.plan.location, output)

    def test_startup_failure_logs_only_exception_type(self):
        sensitive_message = "민감한 병원 일정 서울시 민감구 비밀로 123"
        stderr = io.StringIO()
        failure_delivery = SimpleNamespace(success=True, error=None)

        with patch.object(main, "load_dotenv_file"), patch.object(
            main, "load_settings", side_effect=RuntimeError(sensitive_message)
        ), patch.object(
            main, "send_failure_notification", return_value=failure_delivery
        ), patch("sys.stderr", stderr):
            result = main.main()

        output = stderr.getvalue()
        self.assertEqual(result, 1)
        self.assertIn("RuntimeError", output)
        self.assertNotIn(sensitive_message, output)


if __name__ == "__main__":
    unittest.main()
