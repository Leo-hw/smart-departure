"""Provider-neutral route segments for notification rendering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RouteSegment:
    mode: str
    distance_meters: int | None = None
    line: str | None = None
    origin: str | None = None
    destination: str | None = None
    stop_count: int | None = None
    departure_time: str | None = None


@dataclass(frozen=True)
class RouteGuide:
    segments: tuple[RouteSegment, ...]
