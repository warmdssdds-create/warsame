"""Position reconciliation: compare local state with exchange state."""

from __future__ import annotations

import structlog
from pybit.unified_trading import HTTP

from bot.config import ExchangeConfig
from bot.exchange import fetch_position

log = structlog.get_logger(__name__)


def reconcile_position(
    session: HTTP,
    cfg: ExchangeConfig,
    local_side: str | None,
) -> dict | None:
    """
    Fetch the actual position from the exchange and warn if it differs
    from our local expectation.

    Returns the live position dict (or None if flat).
    """
    live = fetch_position(session, cfg.symbol, cfg.category)

    live_side = live.get("side") if live else None

    if local_side != live_side:
        log.warning(
            "position_mismatch",
            local_side=local_side,
            exchange_side=live_side,
            symbol=cfg.symbol,
        )

    return live
