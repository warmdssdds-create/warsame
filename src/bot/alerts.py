"""Alerting: Telegram notifications."""

from __future__ import annotations

import structlog

from bot.config import AlertConfig

log = structlog.get_logger(__name__)


def send_alert(cfg: AlertConfig, message: str) -> None:
    """Send a Telegram message if credentials are configured."""
    if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
        return

    try:
        import httpx  # lazy import – optional dependency

        url = f"https://api.telegram.org/bot{cfg.telegram_bot_token}/sendMessage"
        resp = httpx.post(
            url,
            json={"chat_id": cfg.telegram_chat_id, "text": message},
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("telegram_alert_failed", status=resp.status_code, body=resp.text)
    except Exception as exc:
        log.warning("telegram_alert_exception", exc=str(exc))
