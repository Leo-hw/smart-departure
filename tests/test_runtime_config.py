from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from shared.config.runtime_config import get_enabled_channels, validate_environment


class RuntimeConfigTests(unittest.TestCase):
    def test_get_enabled_channels_normalizes_unique_values(self):
        settings = {
            "notification": {
                "enabled_channels": [" Discord ", "telegram", "discord"],
            }
        }
        self.assertEqual(get_enabled_channels(settings), ["discord", "telegram"])

    def test_validate_environment_requires_only_enabled_channel_vars(self):
        settings = {
            "notification": {
                "enabled_channels": ["discord"],
            }
        }
        env = {
            "GOOGLE_SERVICE_ACCOUNT_JSON": '{"type":"service_account"}',
            "GOOGLE_CALENDAR_IDS": "primary",
            "GOOGLE_MAPS_API_KEY": "maps-key",
            "HOME_ADDRESS": "Seoul",
            "DISCORD_WEBHOOK_URL": "https://discord.test/webhook",
        }

        with patch.dict(os.environ, env, clear=True):
            validated = validate_environment(settings)

        self.assertIn("DISCORD_WEBHOOK_URL", validated)
        self.assertNotIn("TELEGRAM_BOT_TOKEN", validated)

    def test_validate_environment_rejects_unsupported_channel(self):
        settings = {
            "notification": {
                "enabled_channels": ["kakao"],
            }
        }
        with self.assertRaisesRegex(RuntimeError, "Unsupported notification channels"):
            validate_environment(settings)


if __name__ == "__main__":
    unittest.main()
