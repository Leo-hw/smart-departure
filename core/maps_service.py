"""Travel-time provider selection and lookup."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_GOOGLE_DIRECTIONS_ENDPOINT = "https://maps.googleapis.com/maps/api/directions/json"
_CACHE_PATH = Path(".runtime") / "travel_cache.json"
_CACHE_TTL = timedelta(hours=6)
_DEFAULT_TRAVEL_TIME_MINUTES = 30


@dataclass(frozen=True)
class TravelResult:
    duration_minutes: int
    is_estimated: bool
    provider: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _cache_key(origin: str, destination: str, transport_mode: str) -> str:
    return f"{origin}|{destination}|{transport_mode}"


def _load_cache() -> Dict[str, Dict[str, Any]]:
    try:
        with _CACHE_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}

    return payload if isinstance(payload, dict) else {}


def _save_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _CACHE_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(_CACHE_PATH)


def _read_fresh_cache(origin: str, destination: str, transport_mode: str) -> Optional[int]:
    cache = _load_cache()
    entry = cache.get(_cache_key(origin, destination, transport_mode))
    if not isinstance(entry, dict):
        return None

    duration = entry.get("duration_minutes")
    cached_at = entry.get("cached_at")
    if not isinstance(duration, int) or not isinstance(cached_at, str):
        return None

    try:
        cached_at_dt = _parse_datetime(cached_at)
    except ValueError:
        return None

    if _utcnow() - cached_at_dt.astimezone(timezone.utc) > _CACHE_TTL:
        return None

    return duration


def _write_cache(origin: str, destination: str, transport_mode: str, duration_minutes: int) -> None:
    cache = _load_cache()
    cache[_cache_key(origin, destination, transport_mode)] = {
        "duration_minutes": duration_minutes,
        "cached_at": _utcnow().isoformat(),
    }
    _save_cache(cache)


def _select_provider(transport_mode: str):
    if transport_mode == "driving":
        return _GoogleMapsProvider()
    return _GoogleMapsProvider()


class _BaseProvider:
    provider_name = "google"

    def calculate(self, origin: str, destination: str, transport_mode: str) -> TravelResult:
        raise NotImplementedError


class _GoogleMapsProvider(_BaseProvider):
    provider_name = "google"

    def calculate(self, origin: str, destination: str, transport_mode: str) -> TravelResult:
        duration_minutes = self._fetch_duration_from_api(origin, destination, transport_mode)
        if duration_minutes is not None:
            _write_cache(origin, destination, transport_mode, duration_minutes)
            return TravelResult(
                duration_minutes=duration_minutes,
                is_estimated=False,
                provider=self.provider_name,
            )

        cached_duration = _read_fresh_cache(origin, destination, transport_mode)
        if cached_duration is not None:
            return TravelResult(
                duration_minutes=cached_duration,
                is_estimated=False,
                provider=self.provider_name,
            )

        return TravelResult(
            duration_minutes=_DEFAULT_TRAVEL_TIME_MINUTES,
            is_estimated=True,
            provider=self.provider_name,
        )

    def _fetch_duration_from_api(
        self, origin: str, destination: str, transport_mode: str
    ) -> Optional[int]:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return None

        params = {
            "origin": origin,
            "destination": destination,
            "mode": transport_mode if transport_mode in {"transit", "driving", "walking"} else "transit",
            "key": api_key,
            "language": "ko",
        }
        if transport_mode in {"transit", "driving"}:
            params["departure_time"] = "now"

        try:
            query_string = urllib.parse.urlencode(params)
            url = f"{_GOOGLE_DIRECTIONS_ENDPOINT}?{query_string}"
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            return None

        if not isinstance(payload, dict) or payload.get("status") != "OK":
            return None

        try:
            return int(payload["routes"][0]["legs"][0]["duration"]["value"] // 60)
        except (KeyError, IndexError, TypeError, ValueError):
            return None


class _KakaoMapsProvider(_BaseProvider):
    provider_name = "kakao"

    def calculate(self, origin: str, destination: str, transport_mode: str) -> TravelResult:
        raise NotImplementedError("Kakao Maps travel time lookup is not implemented yet.")


def get_travel_time(origin: str, destination: str, transport_mode: str) -> TravelResult:
    """Return travel time information for the given transport mode."""
    provider = _select_provider(transport_mode)
    return provider.calculate(origin, destination, transport_mode)
