from __future__ import annotations

import unittest
from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/departure_check.yml")


class WorkflowConfigTests(unittest.TestCase):
    def test_departure_check_uses_five_minute_schedule_and_manual_trigger(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn('cron: "*/5 * * * *"', workflow)
        self.assertIn("workflow_dispatch:", workflow)

    def test_departure_check_uses_pip_cache_and_concurrency_guard(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn('cache: "pip"', workflow)
        self.assertIn("concurrency:", workflow)
        self.assertIn("group: departure-check", workflow)
        self.assertIn("cancel-in-progress: false", workflow)

    def test_runtime_cache_contains_only_hashed_dedup_state(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("path: .runtime/sent_alerts.json", workflow)
        self.assertNotIn("path: .runtime\n", workflow)


if __name__ == "__main__":
    unittest.main()
