"""TTL-based deduplication for sent alerts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from core.departure_engine import DepartureDecision

KST = ZoneInfo("Asia/Seoul")
SENT_ALERTS_PATH = Path(".runtime") / "sent_alerts.json"


def filter_pending_decisions(
    decisions: Iterable[DepartureDecision],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> tuple[list[DepartureDecision], list[DepartureDecision]]:
    """Split alertable decisions into pending and dedup-skipped sets."""
    current_time = _ensure_kst(now or _current_time_kst())
    ttl = timedelta(minutes=int(settings.get("schedule", {}).get("dedup_ttl_minutes", 0)))
    sent_alerts = _load_sent_alerts()
    active_alerts = _prune_expired_records(sent_alerts, ttl, current_time)

    pending: list[DepartureDecision] = []
    skipped: list[DepartureDecision] = []
    for decision in decisions:
        if _is_duplicate(decision, active_alerts, ttl, current_time):
            skipped.append(decision)
        else:
            pending.append(decision)

    _save_sent_alerts(active_alerts)
    return pending, skipped


def mark_successful_deliveries(
    delivered_decisions: Iterable[DepartureDecision],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> None:
    """Persist successful notification records for future dedup checks."""
    current_time = _ensure_kst(now or _current_time_kst())
    ttl = timedelta(minutes=int(settings.get("schedule", {}).get("dedup_ttl_minutes", 0)))
    sent_alerts = _prune_expired_records(_load_sent_alerts(), ttl, current_time)

    for decision in delivered_decisions:
        sent_alerts[decision.event.event_id] = {
            "sent_at": current_time.isoformat(),
            "departure_time": decision.departure_time.isoformat(),
        }

    _save_sent_alerts(sent_alerts)


def _is_duplicate(
    decision: DepartureDecision,
    sent_alerts: dict[str, dict[str, Any]],
    ttl: timedelta,
    now: datetime,
) -> bool:
    record = sent_alerts.get(decision.event.event_id)
    if not isinstance(record, dict):
        return False

    sent_at = record.get("sent_at")
    if not isinstance(sent_at, str):
        return False

    try:
        sent_at_dt = _parse_datetime(sent_at)
    except ValueError:
        return False

    return now - sent_at_dt <= ttl


def _load_sent_alerts() -> dict[str, dict[str, Any]]:
    try:
        with SENT_ALERTS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}

    return payload if isinstance(payload, dict) else {}


def _save_sent_alerts(sent_alerts: dict[str, dict[str, Any]]) -> None:
    SENT_ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SENT_ALERTS_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(sent_alerts, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(SENT_ALERTS_PATH)


def _prune_expired_records(
    sent_alerts: dict[str, dict[str, Any]],
    ttl: timedelta,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    if ttl.total_seconds() <= 0:
        return {}

    active_records: dict[str, dict[str, Any]] = {}
    for event_id, record in sent_alerts.items():
        if not isinstance(record, dict):
            continue
        sent_at = record.get("sent_at")
        if not isinstance(sent_at, str):
            continue
        try:
            sent_at_dt = _parse_datetime(sent_at)
        except ValueError:
            continue
        if now - sent_at_dt <= ttl:
            active_records[event_id] = record
    return active_records


def _current_time_kst() -> datetime:
    return datetime.now(tz=KST)


def _ensure_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _parse_datetime(value: str) -> datetime:
    return _ensure_kst(datetime.fromisoformat(value.replace("Z", "+00:00")))
