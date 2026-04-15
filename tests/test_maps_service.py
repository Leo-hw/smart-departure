import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from core import maps_service


class MapsServiceTests(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tempdir.name) / "travel_cache.json"
        self.fixed_now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self._tempdir.cleanup()

    def _patch_context(self):
        return patch.multiple(
            maps_service,
            _CACHE_PATH=self.cache_path,
            _utcnow=Mock(return_value=self.fixed_now),
        )

    def test_get_travel_time_uses_google_api_and_writes_cache(self):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "status": "OK",
                "routes": [
                    {
                        "legs": [
                            {
                                "duration": {
                                    "value": 2100,
                                }
                            }
                        ]
                    }
                ],
            }
        ).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = None

        expected_url = (
            "https://maps.googleapis.com/maps/api/directions/json?"
            "origin=Seoul+Station&destination=Gangnam+Station&mode=transit"
            "&key=test-key&language=ko&departure_time=now"
        )

        with self._patch_context(), patch.dict(
            "os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False
        ), patch.object(maps_service.urllib.request, "urlopen", return_value=response) as mock_urlopen:
            result = maps_service.get_travel_time("Seoul Station", "Gangnam Station", "transit")

        self.assertEqual(result.duration_minutes, 35)
        self.assertFalse(result.is_estimated)
        self.assertEqual(result.provider, "google")
        mock_urlopen.assert_called_once()
        self.assertEqual(mock_urlopen.call_args.args[0], expected_url)
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 10)

        cache_data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(
            cache_data["Seoul Station|Gangnam Station|transit"]["duration_minutes"], 35
        )

    def test_get_travel_time_falls_back_to_cache_when_api_fails(self):
        cache_payload = {
            "Home|Office|transit": {
                "duration_minutes": 42,
                "cached_at": self.fixed_now.isoformat(),
            }
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")

        with self._patch_context(), patch.dict(
            "os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False
        ), patch.object(
            maps_service.urllib.request,
            "urlopen",
            side_effect=maps_service.urllib.error.URLError("network down"),
        ):
            result = maps_service.get_travel_time("Home", "Office", "transit")

        self.assertEqual(result.duration_minutes, 42)
        self.assertFalse(result.is_estimated)
        self.assertEqual(result.provider, "google")

    def test_get_travel_time_returns_default_when_api_and_cache_fail(self):
        stale_cache_payload = {
            "Home|Office|transit": {
                "duration_minutes": 42,
                "cached_at": (self.fixed_now - timedelta(hours=7)).isoformat(),
            }
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(stale_cache_payload), encoding="utf-8")

        with self._patch_context(), patch.dict(
            "os.environ", {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False
        ), patch.object(
            maps_service.urllib.request,
            "urlopen",
            side_effect=maps_service.urllib.error.URLError("network down"),
        ):
            result = maps_service.get_travel_time("Home", "Office", "transit")

        self.assertEqual(result.duration_minutes, 30)
        self.assertTrue(result.is_estimated)
        self.assertEqual(result.provider, "google")

    def test_get_travel_time_returns_default_when_api_key_missing(self):
        with self._patch_context(), patch.dict("os.environ", {}, clear=True):
            result = maps_service.get_travel_time("Home", "Office", "transit")

        self.assertEqual(result.duration_minutes, 30)
        self.assertTrue(result.is_estimated)
        self.assertEqual(result.provider, "google")


if __name__ == "__main__":
    unittest.main()
