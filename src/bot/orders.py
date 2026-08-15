"""Order execution and management layer."""

from __future__ import annotations

import structlog
from pybit.unified_trading import HTTP

from bot.config import BotConfig
from bot.exchange import fetch_position, place_order, set_leverage
from bot.risk import TradeParams
from bot.signals import Direction

log = structlog.get_logger(__name__)


def open_position(
    session: HTTP,
    cfg: BotConfig,
    direction: Direction,
    params: TradeParams,
) -> dict | None:
    """Open a new position.  Returns order result or None if dry_run."""
    symbol = cfg.exchange.symbol
    category = cfg.exchange.category
    side = "Buy" if direction == Direction.LONG else "Sell"

    if cfg.dry_run:
        log.info(
            "dry_run_open",
            side=side,
            qty=params.qty,
            sl=params.stop_loss,
            tp=params.take_profit,
        )
        return None

    # Set leverage before entering
    try:
        set_leverage(session, symbol, params.leverage, category)
    except Exception as exc:
        log.warning("leverage_set_failed", exc=str(exc))

    result = place_order(
        session=session,
        symbol=symbol,
        side=side,
        qty=params.qty,
        order_type="Market",
        category=category,
        stop_loss=params.stop_loss,
        take_profit=params.take_profit,
    )
    return result


def close_position(
    session: HTTP,
    cfg: BotConfig,
    current_pos: dict,
) -> dict | None:
    """Close an open position with a reduce-only market order."""
    symbol = cfg.exchange.symbol
    category = cfg.exchange.category

    size = float(current_pos.get("size", 0))
    if size == 0:
        return None

    pos_side = current_pos.get("side", "Buy")  # "Buy" means long
    close_side = "Sell" if pos_side == "Buy" else "Buy"

    if cfg.dry_run:
        log.info("dry_run_close", symbol=symbol, close_side=close_side, size=size)
        return None

    result = place_order(
        session=session,
        symbol=symbol,
        side=close_side,
        qty=size,
        order_type="Market",
        category=category,
        reduce_only=True,
    )
    return result


def check_and_exit_conditions(
    session: HTTP,
    cfg: BotConfig,
    current_pos: dict | None,
    direction: Direction,
) -> bool:
    """
    Returns True if the strategy wants to exit the current position.

    Currently: exit if signal direction has flipped against open position.
    (SL/TP are managed by the exchange via attached orders.)
    """
    if current_pos is None:
        return False

    pos_side = current_pos.get("side", "")
    if pos_side == "Buy" and direction == Direction.SHORT:
        log.info("exit_signal_flip", reason="short_signal_while_long")
        return True
    if pos_side == "Sell" and direction == Direction.LONG:
        log.info("exit_signal_flip", reason="long_signal_while_short")
        return True
    return False
