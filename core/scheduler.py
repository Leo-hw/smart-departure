"""Daily schedule planning and due-alert extraction."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from core.calendar_service import CalendarEvent, get_upcoming_events
from core.departure_engine import DepartureDecision, build_departure_decisions

KST = ZoneInfo("Asia/Seoul")
SCHEDULE_TODAY_PATH = Path(".runtime") / "schedule_today.json"
SNAPSHOT_VERSION = 3


@dataclass(frozen=True)
class PrepStage:
    label: str
    alert_time: datetime

    @property
    def stage_id(self) -> str:
        return self.label


@dataclass(frozen=True)
class SchedulePlan:
    event_id: str
    summary: str
    location: str
    event_start: datetime
    travel_minutes: int
    is_estimated: bool
    departure_time: datetime
    prep_alert_time: datetime | None
    transport_mode: str
    provider: str
    buffer_minutes: int
    occasion: str = "casual"
    stages: tuple[PrepStage, ...] = ()
    travel_source: str = "api"
    trusted_travel_minutes: int | None = None


@dataclass(frozen=True)
class ScheduledAlert:
    alert_type: str
    alert_time: datetime
    plan: SchedulePlan
    classification: str = "on_time"
    evaluated_at: datetime | None = None
    stage_id: str | None = None
    stage_label: str | None = None

    @property
    def dedup_key(self) -> str:
        key = f"{self.plan.event_id}:{self.plan.event_start.isoformat()}:{self.alert_type}"
        return f"{key}:{self.stage_id}" if self.stage_id is not None else key

    @property
    def event_id(self) -> str:
        return self.plan.event_id

    @property
    def is_late(self) -> bool:
        return self.classification == "catch_up"


def load_or_build_daily_schedule(
    settings: dict[str, Any],
    now: datetime | None = None,
) -> list[SchedulePlan]:
    """Rebuild today's plans unless a configured snapshot TTL allows reuse."""
    current_time = _ensure_kst(now or _current_time_kst())
    snapshot_ttl_minutes = int(
        settings.get("schedule", {}).get("snapshot_ttl_minutes", 0)
    )
    snapshot = _load_schedule_snapshot()
    if _snapshot_is_fresh(snapshot, current_time, snapshot_ttl_minutes):
        return _deserialize_plans(snapshot.get("plans", []))

    prior_plans = (
        _deserialize_plans(snapshot.get("plans", []))
        if snapshot.get("version") == SNAPSHOT_VERSION
        and snapshot.get("date") == current_time.date().isoformat()
        else []
    )
    plans = build_daily_plans(settings, now=current_time, prior_plans=prior_plans)
    _save_schedule_snapshot(current_time, plans)
    return plans


def build_daily_plans(
    settings: dict[str, Any],
    now: datetime | None = None,
    events: Iterable[CalendarEvent] | None = None,
    prior_plans: Iterable[SchedulePlan] = (),
) -> list[SchedulePlan]:
    """Create today's schedule plans from calendar events and travel times."""
    current_time = _ensure_kst(now or _current_time_kst())
    source_events = list(events) if events is not None else _get_today_events(current_time)
    prior_by_id = {plan.event_id: plan for plan in prior_plans}
    decisions = build_departure_decisions(source_events, now=current_time)
    plans: list[SchedulePlan] = []
    for decision in decisions:
        if decision.event.start_time.date() != current_time.date():
            continue
        travel_minutes, trusted_minutes, is_estimated = _stable_transit_minutes(
            decision, prior_by_id.get(decision.event.event_id)
        )
        departure_time = decision.event.start_time - timedelta(
            minutes=travel_minutes + decision.buffer_minutes
        )
        occasion = classify_occasion(decision.event, settings)
        stages = _build_stages(occasion, departure_time, settings)
        plans.append(
            SchedulePlan(
                event_id=decision.event.event_id,
                summary=decision.event.summary,
                location=decision.event.location,
                event_start=decision.event.start_time,
                travel_minutes=travel_minutes,
                is_estimated=is_estimated,
                departure_time=departure_time,
                prep_alert_time=None,
                transport_mode=decision.transport_mode,
                provider=decision.provider,
                buffer_minutes=decision.buffer_minutes,
                occasion=occasion,
                stages=stages,
                travel_source=decision.travel_source,
                trusted_travel_minutes=trusted_minutes,
            )
        )

    plans.sort(key=lambda item: item.departure_time)
    return plans


def _stable_transit_minutes(
    decision: DepartureDecision, prior: SchedulePlan | None
) -> tuple[int, int | None, bool]:
    if decision.transport_mode != "transit":
        return decision.travel_minutes, None, decision.is_estimated

    same_trip = (
        prior is not None
        and prior.event_start == decision.event.start_time
        and prior.location == decision.event.location
        and prior.transport_mode == decision.transport_mode
        and prior.provider == decision.provider
    )
    trusted = prior.trusted_travel_minutes if same_trip else None
    if decision.travel_source == "api" and not decision.is_estimated:
        trusted = max(trusted or 0, decision.travel_minutes)

    effective = trusted if trusted is not None else decision.travel_minutes
    estimated = (
        decision.is_estimated
        or decision.travel_source != "api"
        or effective != decision.travel_minutes
    )
    return effective, trusted, estimated


def get_due_alerts(
    plans: Iterable[SchedulePlan],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> list[ScheduledAlert]:
    """Return deliverable alerts, keeping only the latest missed prep stage."""
    candidates = get_alert_candidates(plans, settings=settings, now=now)
    selected, _ = select_latest_prep_alerts(candidates, now=now)
    return selected


def get_alert_candidates(
    plans: Iterable[SchedulePlan],
    settings: dict[str, Any],
    now: datetime | None = None,
) -> list[ScheduledAlert]:
    """Return on-time and catch-up alert candidates before dedup selection."""
    current_time = _ensure_kst(now or _current_time_kst())

    candidates: list[ScheduledAlert] = []
    for plan in plans:
        for stage in _get_prep_stages(plan):
            alert = ScheduledAlert(
                alert_type="prep", alert_time=stage.alert_time, plan=plan,
                stage_id=stage.stage_id, stage_label=stage.label,
            )
            classification = classify_alert(alert, current_time, settings)
            if classification in {"on_time", "catch_up"}:
                candidates.append(
                    ScheduledAlert(
                        alert_type=alert.alert_type,
                        alert_time=alert.alert_time,
                        plan=alert.plan,
                        classification=classification,
                        evaluated_at=current_time,
                        stage_id=alert.stage_id,
                        stage_label=alert.stage_label,
                    )
                )

        alert = ScheduledAlert(alert_type="departure", alert_time=plan.departure_time, plan=plan)
        classification = classify_alert(alert, current_time, settings)
        if classification in {"on_time", "catch_up"}:
            candidates.append(
                ScheduledAlert(
                    alert_type=alert.alert_type,
                    alert_time=alert.alert_time,
                    plan=alert.plan,
                    classification=classification,
                    evaluated_at=current_time,
                )
            )

    candidates.sort(key=lambda item: item.alert_time)
    return candidates


def classify_alert(
    alert: ScheduledAlert,
    now: datetime,
    settings: dict[str, Any],
) -> str:
    """Classify an alert relative to its on-time window and catch-up expiry."""
    current_time = _ensure_kst(now)
    target_time = _ensure_kst(alert.alert_time)
    window_minutes = int(settings.get("schedule", {}).get("alert_window_minutes", 0))
    window_delta = timedelta(minutes=window_minutes)
    on_time_start = target_time - window_delta
    on_time_end = target_time + window_delta
    departure_catchup_minutes = int(
        settings.get("schedule", {}).get("departure_catchup_minutes", 45)
    )
    expiry = (
        alert.plan.departure_time
        if alert.alert_type == "prep"
        else max(
            alert.plan.departure_time + timedelta(minutes=departure_catchup_minutes),
            alert.plan.event_start,
        )
    )

    if current_time < on_time_start:
        return "pending"
    if current_time <= on_time_end:
        return "on_time"
    if current_time <= expiry:
        return "catch_up"
    return "expired"


def select_latest_prep_alerts(
    alerts: Iterable[ScheduledAlert],
    now: datetime | None = None,
) -> tuple[list[ScheduledAlert], list[ScheduledAlert]]:
    """Select the latest eligible prep per event and seal older prep stages."""
    alerts_list = list(alerts)
    selected: list[ScheduledAlert] = [alert for alert in alerts_list if alert.alert_type != "prep"]
    sealed: list[ScheduledAlert] = []

    prep_by_event: dict[str, list[ScheduledAlert]] = {}
    for alert in alerts_list:
        if alert.alert_type == "prep":
            prep_by_event.setdefault(alert.event_id, []).append(alert)

    for event_alerts in prep_by_event.values():
        latest = max(event_alerts, key=lambda item: item.alert_time)
        selected.append(latest)
        sealed.extend(alert for alert in event_alerts if alert is not latest)

    selected.sort(key=lambda item: item.alert_time)
    sealed.sort(key=lambda item: item.alert_time)
    return selected, sealed


def classify_occasion(event: CalendarEvent, settings: dict[str, Any]) -> str:
    profiles = settings.get("prep_profiles", {})
    override = event.occasion_override
    if override in profiles:
        return override
    for name in ("formal", "semi_formal", "travel", "sports"):
        keywords = profiles.get(name, {}).get("keywords", [])
        if any(str(keyword).casefold() in event.summary.casefold() for keyword in keywords):
            return name
    return "casual"


def _build_stages(
    occasion: str, departure_time: datetime, settings: dict[str, Any]
) -> tuple[PrepStage, ...]:
    raw_stages = settings.get("prep_profiles", {}).get(occasion, {}).get("stages", [])
    stages: list[PrepStage] = []
    seen_labels: set[str] = set()
    for raw in raw_stages:
        label = str(raw["label"]).strip()
        minutes = int(raw["minutes_before_departure"])
        if not label or label in seen_labels or minutes < 0:
            raise ValueError(f"Invalid prep stage in profile {occasion}")
        seen_labels.add(label)
        if minutes > 0:
            stages.append(PrepStage(label, departure_time - timedelta(minutes=minutes)))
    return tuple(sorted(stages, key=lambda stage: stage.alert_time))


def _get_prep_stages(plan: SchedulePlan) -> list[PrepStage]:
    if plan.stages:
        return list(plan.stages)
    return [PrepStage("준비 시작", plan.prep_alert_time)] if plan.prep_alert_time else []


def _get_today_events(current_time: datetime) -> list[CalendarEvent]:
    end_of_day = datetime.combine(current_time.date(), time.max, tzinfo=KST)
    remaining_seconds = max(0, int((end_of_day - current_time).total_seconds()))
    remaining_hours = max(1, int((remaining_seconds + 3599) / 3600))
    return get_upcoming_events(lookahead_hours=remaining_hours)


def _load_schedule_snapshot() -> dict[str, Any]:
    try:
        with SCHEDULE_TODAY_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _snapshot_is_fresh(
    snapshot: dict[str, Any],
    now: datetime,
    ttl_minutes: int,
) -> bool:
    if ttl_minutes <= 0 or snapshot.get("date") != now.date().isoformat() or snapshot.get("version") != SNAPSHOT_VERSION:
        return False

    built_at = snapshot.get("built_at")
    if not isinstance(built_at, str):
        return False

    try:
        built_at_time = _parse_datetime(built_at)
    except ValueError:
        return False

    age = now - built_at_time
    return timedelta(0) <= age <= timedelta(minutes=ttl_minutes)


def _save_schedule_snapshot(built_at: datetime, plans: list[SchedulePlan]) -> None:
    SCHEDULE_TODAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SNAPSHOT_VERSION,
        "date": built_at.date().isoformat(),
        "built_at": built_at.isoformat(),
        "plans": [_serialize_plan(plan) for plan in plans],
    }
    tmp_path = SCHEDULE_TODAY_PATH.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(SCHEDULE_TODAY_PATH)


def _serialize_plan(plan: SchedulePlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["event_start"] = plan.event_start.isoformat()
    payload["departure_time"] = plan.departure_time.isoformat()
    payload.pop("prep_alert_time")
    payload["stages"] = [
        {
            "label": stage.label,
            "alert_time": stage.alert_time.isoformat(),
            "alert_key": ScheduledAlert("prep", stage.alert_time, plan, stage_id=stage.stage_id).dedup_key,
        }
        for stage in plan.stages
    ] + [{
        "label": "출발",
        "alert_time": plan.departure_time.isoformat(),
        "alert_key": ScheduledAlert("departure", plan.departure_time, plan).dedup_key,
    }]
    return payload


def _deserialize_plans(raw_plans: Iterable[dict[str, Any]]) -> list[SchedulePlan]:
    plans: list[SchedulePlan] = []
    for raw_plan in raw_plans:
        if not isinstance(raw_plan, dict):
            continue
        plans.append(
            SchedulePlan(
                event_id=str(raw_plan["event_id"]),
                summary=str(raw_plan["summary"]),
                location=str(raw_plan["location"]),
                event_start=_parse_datetime(str(raw_plan["event_start"])),
                travel_minutes=int(raw_plan["travel_minutes"]),
                is_estimated=bool(raw_plan["is_estimated"]),
                departure_time=_parse_datetime(str(raw_plan["departure_time"])),
                prep_alert_time=None,
                transport_mode=str(raw_plan["transport_mode"]),
                provider=str(raw_plan["provider"]),
                buffer_minutes=int(raw_plan["buffer_minutes"]),
                occasion=str(raw_plan.get("occasion", "casual")),
                stages=tuple(
                    PrepStage(str(stage["label"]), _parse_datetime(str(stage["alert_time"])))
                    for stage in raw_plan.get("stages", []) if stage.get("label") != "출발"
                ),
                travel_source=str(raw_plan.get("travel_source", "api")),
                trusted_travel_minutes=(
                    int(raw_plan["trusted_travel_minutes"])
                    if raw_plan.get("trusted_travel_minutes") is not None else None
                ),
            )
        )
    return plans


def _current_time_kst() -> datetime:
    return datetime.now(tz=KST)


def _ensure_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _parse_datetime(value: str) -> datetime:
    return _ensure_kst(datetime.fromisoformat(value.replace("Z", "+00:00")))
