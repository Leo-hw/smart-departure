from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.config.runtime_config import load_dotenv_file


class RuntimeEnvLoadingTests(unittest.TestCase):
    def test_load_dotenv_file_sets_missing_values_only(self):
        with tempfile.TemporaryDirectory() as tempdir:
            env_path = Path(tempdir) / ".env"
            env_path.write_text(
                "DISCORD_WEBHOOK_URL=https://discord.test/webhook\nHOME_ADDRESS='Seoul Station'\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"HOME_ADDRESS": "Existing Home"}, clear=True):
                load_dotenv_file(env_path)
                self.assertEqual(os.environ["DISCORD_WEBHOOK_URL"], "https://discord.test/webhook")
                self.assertEqual(os.environ["HOME_ADDRESS"], "Existing Home")


if __name__ == "__main__":
    unittest.main()
