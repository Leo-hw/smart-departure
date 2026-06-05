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

    def test_driving_selects_kakao_provider(self):
        provider = maps_service._select_provider("driving")

        self.assertIsInstance(provider, maps_service._KakaoMapsProvider)
        self.assertIsInstance(maps_service._select_provider("transit"), maps_service._GoogleMapsProvider)
        self.assertIsInstance(maps_service._select_provider("walking"), maps_service._GoogleMapsProvider)

    def test_driving_uses_kakao_geocoding_and_directions(self):
        responses = [
            self._json_response({"documents": [{"x": "126.9707", "y": "37.5547"}]}),
            self._json_response({"documents": [{"x": "127.0276", "y": "37.4979"}]}),
            self._json_response({"routes": [{"summary": {"duration": 1980}}]}),
        ]

        with self._patch_context(), patch.dict(
            "os.environ", {"KAKAO_REST_API_KEY": "kakao-key"}, clear=False
        ), patch.object(
            maps_service.urllib.request,
            "urlopen",
            side_effect=responses,
        ) as mock_urlopen:
            result = maps_service.get_travel_time(
                "서울역",
                "강남역",
                "driving",
            )

        self.assertEqual(result.duration_minutes, 33)
        self.assertFalse(result.is_estimated)
        self.assertEqual(result.provider, "kakao")
        self.assertEqual(mock_urlopen.call_count, 3)

        requests = [call.args[0] for call in mock_urlopen.call_args_list]
        self.assertEqual(requests[0].get_header("Authorization"), "KakaoAK kakao-key")
        self.assertEqual(
            requests[0].full_url,
            "https://dapi.kakao.com/v2/local/search/address.json?"
            "query=%EC%84%9C%EC%9A%B8%EC%97%AD",
        )
        self.assertEqual(
            requests[1].full_url,
            "https://dapi.kakao.com/v2/local/search/address.json?"
            "query=%EA%B0%95%EB%82%A8%EC%97%AD",
        )
        self.assertEqual(
            requests[2].full_url,
            "https://apis-navi.kakaomobility.com/v1/directions?"
            "origin=126.9707%2C37.5547&destination=127.0276%2C37.4979"
            "&priority=RECOMMEND",
        )

        cache_data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(cache_data["서울역|강남역|driving"]["duration_minutes"], 33)

    def test_driving_failures_fall_back_to_fresh_cache(self):
        cache_payload = {
            "Home|Office|driving": {
                "duration_minutes": 24,
                "cached_at": self.fixed_now.isoformat(),
            }
        }
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")

        failure_cases = {
            "missing key": (
                {},
                [],
            ),
            "geocode failure": (
                {"KAKAO_REST_API_KEY": "kakao-key"},
                [self._json_response({"documents": []})],
            ),
            "directions failure": (
                {"KAKAO_REST_API_KEY": "kakao-key"},
                [
                    self._json_response({"documents": [{"x": "126.9", "y": "37.5"}]}),
                    self._json_response({"documents": [{"x": "127.0", "y": "37.4"}]}),
                    maps_service.urllib.error.URLError("network down"),
                ],
            ),
        }

        for name, (environment, side_effects) in failure_cases.items():
            with self.subTest(name=name), self._patch_context(), patch.dict(
                "os.environ", environment, clear=True
            ), patch.object(
                maps_service.urllib.request,
                "urlopen",
                side_effect=side_effects,
            ):
                result = maps_service.get_travel_time("Home", "Office", "driving")

            self.assertEqual(result.duration_minutes, 24)
            self.assertFalse(result.is_estimated)
            self.assertEqual(result.provider, "kakao")

    def test_driving_returns_estimate_when_api_and_cache_fail(self):
        with self._patch_context(), patch.dict(
            "os.environ", {"KAKAO_REST_API_KEY": "kakao-key"}, clear=True
        ), patch.object(
            maps_service.urllib.request,
            "urlopen",
            return_value=self._json_response({"documents": []}),
        ):
            result = maps_service.get_travel_time("Home", "Office", "driving")

        self.assertEqual(result.duration_minutes, 30)
        self.assertTrue(result.is_estimated)
        self.assertEqual(result.provider, "kakao")

    @staticmethod
    def _json_response(payload):
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        response.__exit__.return_value = None
        return response


if __name__ == "__main__":
    unittest.main()
