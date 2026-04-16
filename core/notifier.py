"""Notification routing and delivery."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from core.departure_engine import DepartureDecision
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


def send_notifications(
    decisions: Iterable[DepartureDecision],
    settings: dict[str, Any] | None = None,
) -> list[NotificationDelivery]:
    """Send decisions to all enabled channels and collect delivery results."""
    runtime_settings = settings or load_settings()
    enabled_channels = get_enabled_channels(runtime_settings)
    if not enabled_channels:
        return []

    deliveries: list[NotificationDelivery] = []
    for decision in decisions:
        message = format_departure_message(decision)
        for channel in enabled_channels:
            deliveries.append(_send_channel(channel, decision, message, runtime_settings))
    return deliveries


def format_departure_message(decision: DepartureDecision) -> str:
    """Render a shared departure alert message for all channels."""
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
        ]
    )


def _send_channel(
    channel: str,
    decision: DepartureDecision,
    message: str,
    settings: dict[str, Any],
) -> NotificationDelivery:
    if channel == "discord":
        return _send_discord(decision, message, settings)
    if channel == "telegram":
        return _send_telegram(decision, message, settings)
    return NotificationDelivery(
        channel=channel,
        event_id=decision.event.event_id,
        success=False,
        error=f"Unsupported notification channel: {channel}",
    )


def _send_discord(
    decision: DepartureDecision,
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
        event_id=decision.event.event_id,
    )


def _send_telegram(
    decision: DepartureDecision,
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
        event_id=decision.event.event_id,
    )


def _post_json(
    url: str | None,
    payload: dict[str, Any],
    channel: str,
    event_id: str,
) -> NotificationDelivery:
    if not url:
        return NotificationDelivery(
            channel=channel,
            event_id=event_id,
            success=False,
            error=f"{CHANNEL_LABELS.get(channel, channel)} configuration is missing",
        )

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = getattr(response, "status", 200)
            if 200 <= status_code < 300:
                return NotificationDelivery(channel=channel, event_id=event_id, success=True)
            return NotificationDelivery(
                channel=channel,
                event_id=event_id,
                success=False,
                error=f"{CHANNEL_LABELS.get(channel, channel)} returned status {status_code}",
            )
    except urllib.error.HTTPError as exc:
        return NotificationDelivery(
            channel=channel,
            event_id=event_id,
            success=False,
            error=f"{CHANNEL_LABELS.get(channel, channel)} returned status {exc.code}",
        )
    except (urllib.error.URLError, OSError) as exc:
        return NotificationDelivery(
            channel=channel,
            event_id=event_id,
            success=False,
            error=f"{CHANNEL_LABELS.get(channel, channel)} request failed: {getattr(exc, 'reason', str(exc))}",
        )


def send_telegram_alert(decision: DepartureDecision) -> NotificationDelivery:
    """Backward-compatible single-channel Telegram sender."""
    return _send_telegram(decision, format_departure_message(decision), load_settings())
