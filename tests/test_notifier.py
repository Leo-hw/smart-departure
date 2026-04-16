from __future__ import annotations

import json
import os
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from core.departure_engine import DepartureDecision
from core.notifier import format_departure_message, send_notifications
from core.calendar_service import CalendarEvent

KST = ZoneInfo("Asia/Seoul")


class _FakeResponse:
    def __init__(self, status: int = 204):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class NotifierTests(unittest.TestCase):
    def setUp(self):
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

    def test_format_departure_message_contains_core_fields(self):
        message = format_departure_message(self.decision)
        self.assertIn("출발할 시간이에요", message)
        self.assertIn("스터디 모임", message)
        self.assertIn("강남구 역삼동 OO카페", message)
        self.assertIn("대중교통 약 35분", message)
        self.assertIn("버퍼 10분", message)

    def test_send_notifications_posts_to_enabled_channels(self):
        settings = {
            "notification": {
                "enabled_channels": ["discord", "telegram"],
                "discord": {"username": "smart-departure"},
                "telegram": {"parse_mode": "Markdown"},
            }
        }
        requests: list[object] = []

        def fake_urlopen(request, timeout=10):
            requests.append(request)
            return _FakeResponse()

        env_patch = {
            "DISCORD_WEBHOOK_URL": "https://discord.test/webhook",
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_CHAT_ID": "chat-id",
        }
        with patch.dict(os.environ, env_patch, clear=False), patch(
            "core.notifier.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            deliveries = send_notifications([self.decision], settings=settings)

        self.assertEqual(len(deliveries), 2)
        self.assertTrue(all(item.success for item in deliveries))
        self.assertEqual(len(requests), 2)

        discord_request = requests[0]
        telegram_request = requests[1]
        self.assertEqual(discord_request.full_url, "https://discord.test/webhook")
        self.assertEqual(telegram_request.full_url, "https://api.telegram.org/botbot-token/sendMessage")

        discord_payload = json.loads(discord_request.data.decode("utf-8"))
        telegram_payload = json.loads(telegram_request.data.decode("utf-8"))
        self.assertEqual(discord_payload["username"], "smart-departure")
        self.assertEqual(telegram_payload["chat_id"], "chat-id")

    def test_send_notifications_continues_when_one_channel_fails(self):
        settings = {
            "notification": {
                "enabled_channels": ["discord", "telegram"],
                "discord": {"username": "smart-departure"},
                "telegram": {"parse_mode": "Markdown"},
            }
        }

        def fake_urlopen(request, timeout=10):
            if "discord" in request.full_url:
                raise OSError("network issue")
            return _FakeResponse(status=200)

        env_patch = {
            "DISCORD_WEBHOOK_URL": "https://discord.test/webhook",
            "TELEGRAM_BOT_TOKEN": "bot-token",
            "TELEGRAM_CHAT_ID": "chat-id",
        }
        with patch.dict(os.environ, env_patch, clear=False), patch(
            "core.notifier.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            deliveries = send_notifications([self.decision], settings=settings)

        self.assertEqual(len(deliveries), 2)
        self.assertFalse(deliveries[0].success)
        self.assertTrue(deliveries[1].success)

    def test_send_notifications_reports_unsupported_channel(self):
        settings = {
            "notification": {
                "enabled_channels": ["kakao"],
            }
        }

        deliveries = send_notifications([self.decision], settings=settings)
        self.assertEqual(len(deliveries), 1)
        self.assertFalse(deliveries[0].success)
        self.assertIn("Unsupported", deliveries[0].error)


if __name__ == "__main__":
    unittest.main()
