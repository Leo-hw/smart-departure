"""Persistent deduplication for sent and intentionally skipped alerts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from core.privacy import short_id

KST = ZoneInfo("Asia/Seoul")
SENT_ALERTS_PATH = Path(".runtime") / "sent_alerts.json"
HASHED_KEY_PATTERN = re.compile(r"^[0-9a-f]{8}$")


def filter_pending_decisions(
    decisions: Iterable[object],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> tuple[list[object], list[object]]:
    """Split alertable items into pending and dedup-skipped sets."""
    current_time = _ensure_kst(now or _current_time_kst())
    sent_alerts = _load_sent_alerts()
    active_alerts = _prune_expired_records(sent_alerts, current_time)

    pending: list[object] = []
    skipped: list[object] = []
    for decision in decisions:
        if _is_duplicate(decision, active_alerts):
            skipped.append(decision)
        else:
            pending.append(decision)

    _save_sent_alerts(active_alerts)
    return pending, skipped


def mark_successful_deliveries(
    delivered_decisions: Iterable[object],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> None:
    """Persist successful notification records for future dedup checks."""
    current_time = _ensure_kst(now or _current_time_kst())
    sent_alerts = _prune_expired_records(_load_sent_alerts(), current_time)

    for decision in delivered_decisions:
        sent_alerts[_get_dedup_key(decision)] = _build_record(
            decision,
            status="sent",
            recorded_at=current_time,
        )

    _save_sent_alerts(sent_alerts)


def mark_skipped_deliveries(
    skipped_decisions: Iterable[object],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> None:
    """Persist prep stages superseded by a more recent missed prep alert."""
    current_time = _ensure_kst(now or _current_time_kst())
    sent_alerts = _prune_expired_records(_load_sent_alerts(), current_time)
    for decision in skipped_decisions:
        sent_alerts[_get_dedup_key(decision)] = _build_record(
            decision,
            status="skipped",
            recorded_at=current_time,
        )
    _save_sent_alerts(sent_alerts)


def _is_duplicate(
    decision: object,
    sent_alerts: dict[str, dict[str, Any]],
) -> bool:
    record = sent_alerts.get(_get_dedup_key(decision))
    return isinstance(record, dict) and record.get("status") in {"sent", "skipped"}


def _load_sent_alerts() -> dict[str, dict[str, Any]]:
    try:
        with SENT_ALERTS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(payload, dict):
        return {}

    sanitized: dict[str, dict[str, Any]] = {}
    for key, record in payload.items():
        if not isinstance(key, str) or not isinstance(record, dict):
            continue
        persisted_key = (
            key
            if HASHED_KEY_PATTERN.fullmatch(key) and "event_id" not in record
            else short_id(key)
        )
        sanitized[persisted_key] = {
            field: value
            for field, value in record.items()
            if field not in {"event_id", "summary", "location"}
        }
    return sanitized


def _save_sent_alerts(sent_alerts: dict[str, dict[str, Any]]) -> None:
    SENT_ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SENT_ALERTS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(sent_alerts, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(SENT_ALERTS_PATH)


def _prune_expired_records(
    sent_alerts: dict[str, dict[str, Any]],
    now: datetime,
) -> dict[str, dict[str, Any]]:
    active_records: dict[str, dict[str, Any]] = {}
    for dedup_key, record in sent_alerts.items():
        if not isinstance(record, dict):
            continue
        event_start = record.get("event_start")
        if not isinstance(event_start, str):
            continue
        try:
            event_start_dt = _parse_datetime(event_start)
        except ValueError:
            continue
        if now <= event_start_dt + timedelta(minutes=60):
            active_records[dedup_key] = record
    return active_records


def _build_record(item: object, status: str, recorded_at: datetime) -> dict[str, Any]:
    return {
        "status": status,
        "sent_at": recorded_at.isoformat(),
        "event_start": _get_event_start(item).isoformat(),
    }


def _current_time_kst() -> datetime:
    return datetime.now(tz=KST)


def _ensure_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _parse_datetime(value: str) -> datetime:
    return _ensure_kst(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _get_dedup_key(item: object) -> str:
    dedup_key = getattr(item, "dedup_key", None)
    if isinstance(dedup_key, str) and dedup_key:
        return short_id(dedup_key)
    return short_id(_get_event_id(item))


def _get_event_id(item: object) -> str:
    direct_event_id = getattr(item, "event_id", None)
    if isinstance(direct_event_id, str) and direct_event_id:
        return direct_event_id

    event = getattr(item, "event", None)
    nested_event_id = getattr(event, "event_id", None)
    if isinstance(nested_event_id, str) and nested_event_id:
        return nested_event_id

    raise RuntimeError("Dedup item does not contain an event_id")


def _get_departure_time(item: object) -> datetime:
    direct_departure = getattr(item, "departure_time", None)
    if isinstance(direct_departure, datetime):
        return _ensure_kst(direct_departure)

    plan = getattr(item, "plan", None)
    planned_departure = getattr(plan, "departure_time", None)
    if isinstance(planned_departure, datetime):
        return _ensure_kst(planned_departure)

    raise RuntimeError("Dedup item does not contain a departure_time")


def _get_event_start(item: object) -> datetime:
    direct_event_start = getattr(item, "event_start", None)
    if isinstance(direct_event_start, datetime):
        return _ensure_kst(direct_event_start)

    plan = getattr(item, "plan", None)
    planned_event_start = getattr(plan, "event_start", None)
    if isinstance(planned_event_start, datetime):
        return _ensure_kst(planned_event_start)

    event = getattr(item, "event", None)
    nested_event_start = getattr(event, "start_time", None)
    if isinstance(nested_event_start, datetime):
        return _ensure_kst(nested_event_start)

    raise RuntimeError("Dedup item does not contain an event_start")
