"""Notification routing and delivery."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from core.departure_engine import DepartureDecision
from core.privacy import safe_exception_label
from core.route_guide import RouteGuide
from core.scheduler import ScheduledAlert
from shared.config.runtime_config import get_enabled_channels, load_settings

CHANNEL_LABELS = {
    "discord": "Discord",
    "telegram": "Telegram",
}

TRANSPORT_LABELS = {
    "transit": "대중교통",
    "driving": "자동차",
    "walking": "도보",
}


@dataclass(frozen=True)
class NotificationDelivery:
    channel: str
    event_id: str
    success: bool
    error: str | None = None
    dedup_key: str | None = None


def send_notifications(
    decisions: Iterable[ScheduledAlert | DepartureDecision],
    settings: dict[str, Any] | None = None,
) -> list[NotificationDelivery]:
    """Send alerts to all enabled channels and collect delivery results."""
    runtime_settings = settings or load_settings()
    enabled_channels = get_enabled_channels(runtime_settings)
    if not enabled_channels:
        return []

    deliveries: list[NotificationDelivery] = []
    for decision in decisions:
        message = (
            format_scheduled_alert_message(decision)
            if isinstance(decision, ScheduledAlert)
            else format_departure_message(decision)
        )
        for channel in enabled_channels:
            deliveries.append(_send_channel(channel, decision, message, runtime_settings))
    return deliveries


def format_departure_message(decision: DepartureDecision) -> str:
    """Render a shared departure alert message for older call sites."""
    transport_label = TRANSPORT_LABELS.get(decision.transport_mode, decision.transport_mode)
    estimate_suffix = " (이동 시간 추정)" if decision.is_estimated else ""
    return "\n".join(
        [
            "🚀 출발할 시간이에요!",
            "",
            f"📅 일정: {decision.event.summary}",
            f"📍 장소: {decision.event.location}",
            f"🕐 시작: {decision.event.start_time.strftime('%Y-%m-%d %H:%M')}",
            f"🚌 이동: {transport_label} 약 {decision.travel_minutes}분{estimate_suffix}",
            f"⏰ 출발: {decision.departure_time.strftime('%Y-%m-%d %H:%M')} (버퍼 {decision.buffer_minutes}분)",
        ] + _format_route_guide(decision.route_guide, decision.provider)
    )


def format_scheduled_alert_message(alert: ScheduledAlert) -> str:
    """Render prep/departure messages from scheduled alert plans."""
    transport_label = TRANSPORT_LABELS.get(alert.plan.transport_mode, alert.plan.transport_mode)
    estimate_suffix = " (이동 시간 추정)" if alert.plan.is_estimated else ""
    route_summary = f"{transport_label} 약 {alert.plan.travel_minutes}분{estimate_suffix}"
    guide_lines = _format_route_guide(
        alert.plan.route_guide, alert.plan.provider,
        include_board_time=alert.alert_type == "departure",
    )
    late_marker = _format_late_marker(alert)

    if alert.alert_type == "prep":
        lines = [
            "🧳 준비를 시작할 시간이에요!",
            late_marker,
            "",
            f"📅 일정: {alert.plan.summary}",
            f"👔 지금: {alert.stage_label}" if alert.stage_label else None,
            f"🕐 준비 시작: {alert.alert_time.strftime('%Y-%m-%d %H:%M')}",
            f"⏰ 출발 예정: {alert.plan.departure_time.strftime('%Y-%m-%d %H:%M')}",
            f"🧭 경로 요약: {route_summary}",
        ]
        return "\n".join(line for line in lines if line is not None) + (
            "\n" + "\n".join(guide_lines) if guide_lines else ""
        )

    lines = [
        "🚀 출발할 시간이에요!",
        late_marker,
        "",
        f"📅 일정: {alert.plan.summary}",
        f"📍 장소: {alert.plan.location}",
        f"🕐 시작: {alert.plan.event_start.strftime('%Y-%m-%d %H:%M')}",
        f"🚌 이동: {route_summary}",
        f"⏰ 출발: {alert.plan.departure_time.strftime('%Y-%m-%d %H:%M')} (버퍼 {alert.plan.buffer_minutes}분)",
        f"🧭 경로 요약: {route_summary}",
    ]
    return "\n".join(line for line in lines if line is not None) + (
        "\n" + "\n".join(guide_lines) if guide_lines else ""
    )


def _format_route_guide(
    guide: RouteGuide | None, provider: str, include_board_time: bool = True
) -> list[str]:
    if guide is None or not guide.segments:
        return []
    lines = ["🗺️ 이동 경로 (현재 조회 기준, 출발 전 재확인):"]
    transit_count = 0
    for segment in guide.segments[:6]:
        if segment.mode == "walk":
            if segment.distance_meters:
                lines.append(f"  • 도보 약 {segment.distance_meters}m")
        elif segment.mode == "transit":
            transfer = "환승 · " if transit_count else ""
            transit_count += 1
            line = _clean_route_text(segment.line) or "대중교통"
            origin = _clean_route_text(segment.origin)
            destination = _clean_route_text(segment.destination)
            path = f"{origin} → {destination}" if origin and destination else origin or destination
            stop_count = f" ({segment.stop_count}정거장)" if segment.stop_count else ""
            board_time = _format_board_time(segment.departure_time) if include_board_time else ""
            lines.append(
                f"  • {transfer}{board_time}{line}: {path}{stop_count}"
                if path else f"  • {transfer}{board_time}{line}"
            )
    if len(guide.segments) > 6:
        lines.append("  • 나머지 구간은 지도 앱에서 확인")
    if provider == "google":
        lines.append("경로 정보: Google Maps")
    return lines


def _clean_route_text(value: str | None) -> str:
    return " ".join(value.split())[:60] if isinstance(value, str) else ""


def _format_board_time(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return parsed.astimezone(ZoneInfo("Asia/Seoul")).strftime("%H:%M ")


def _format_late_marker(alert: ScheduledAlert) -> str | None:
    if not alert.is_late:
        return None
    now = alert.evaluated_at
    if now is None:
        return None
    return (
        "⚠️ 늦었어요 — 원래 "
        f"{alert.alert_time.strftime('%Y-%m-%d %H:%M')} 예정, "
        f"지금 {now.strftime('%Y-%m-%d %H:%M')}"
    )


def _send_channel(
    channel: str,
    decision: ScheduledAlert | DepartureDecision,
    message: str,
    settings: dict[str, Any],
) -> NotificationDelivery:
    if channel == "discord":
        return _send_discord(decision, message, settings)
    if channel == "telegram":
        return _send_telegram(decision, message, settings)
    return NotificationDelivery(
        channel=channel,
        event_id=_extract_event_id(decision),
        success=False,
        error=f"Unsupported notification channel: {channel}",
    )


def _send_discord(
    decision: ScheduledAlert | DepartureDecision,
    message: str,
    settings: dict[str, Any],
) -> NotificationDelivery:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    username = str(settings.get("notification", {}).get("discord", {}).get("username", "smart-departure"))
    payload = {
        "content": message,
        "username": username,
    }
    return _post_json(
        url=webhook_url,
        payload=payload,
        channel="discord",
        event_id=_extract_event_id(decision),
        dedup_key=_extract_dedup_key(decision),
    )


def _send_telegram(
    decision: ScheduledAlert | DepartureDecision,
    message: str,
    settings: dict[str, Any],
) -> NotificationDelivery:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    parse_mode = str(settings.get("notification", {}).get("telegram", {}).get("parse_mode", "Markdown"))
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage" if bot_token else None
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
    }
    return _post_json(
        url=url,
        payload=payload,
        channel="telegram",
        event_id=_extract_event_id(decision),
        dedup_key=_extract_dedup_key(decision),
    )


def _post_json(
    url: str | None,
    payload: dict[str, Any],
    channel: str,
    event_id: str,
    dedup_key: str | None = None,
) -> NotificationDelivery:
    if not url:
        return NotificationDelivery(
            channel=channel,
            event_id=event_id,
            success=False,
            error=f"{CHANNEL_LABELS.get(channel, channel)} configuration is missing",
            dedup_key=dedup_key,
        )

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "smart-departure/1.0 (+https://github.com/Leo-hw/smart-departure)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                return NotificationDelivery(
                    channel=channel,
                    event_id=event_id,
                    success=True,
                    dedup_key=dedup_key,
                )
            return NotificationDelivery(
                channel=channel,
                event_id=event_id,
                success=False,
                error=f"{CHANNEL_LABELS.get(channel, channel)} returned status {status_code}",
                dedup_key=dedup_key,
            )
    except urllib.error.HTTPError as exc:
        return NotificationDelivery(
            channel=channel,
            event_id=event_id,
            success=False,
            error=f"{CHANNEL_LABELS.get(channel, channel)} returned status {exc.code}",
            dedup_key=dedup_key,
        )
    except (urllib.error.URLError, OSError) as exc:
        return NotificationDelivery(
            channel=channel,
            event_id=event_id,
            success=False,
            error=(
                f"{CHANNEL_LABELS.get(channel, channel)} request failed: "
                f"{safe_exception_label(exc)}"
            ),
            dedup_key=dedup_key,
        )


def send_failure_notification(
    exc: Exception,
    settings: dict[str, Any] | None = None,
) -> NotificationDelivery:
    """Send an execution failure directly to Discord without dedup or recursion."""
    username = str(
        (settings or {}).get("notification", {}).get("discord", {}).get(
            "username", "smart-departure"
        )
    )
    return _post_json(
        url=os.environ.get("DISCORD_WEBHOOK_URL"),
        payload={
            "content": (
                "[smart-departure] 실행 실패: "
                f"{safe_exception_label(exc)}"
            ),
            "username": username,
        },
        channel="discord",
        event_id="runtime-error",
    )


def send_telegram_alert(decision: DepartureDecision) -> NotificationDelivery:
    """Backward-compatible single-channel Telegram sender."""
    return _send_telegram(decision, format_departure_message(decision), load_settings())


def _extract_event_id(decision: ScheduledAlert | DepartureDecision) -> str:
    if isinstance(decision, ScheduledAlert):
        return decision.plan.event_id
    return decision.event.event_id


def _extract_dedup_key(decision: ScheduledAlert | DepartureDecision) -> str:
    if isinstance(decision, ScheduledAlert):
        return decision.dedup_key
    return decision.event.event_id
