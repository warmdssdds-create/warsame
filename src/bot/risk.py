"""Risk management: position sizing, SL/TP calculation."""

from __future__ import annotations

from dataclasses import dataclass

from bot.config import RiskConfig


@dataclass
class TradeParams:
    qty: float        # contract base units (e.g. ETC)
    stop_loss: float  # absolute price
    take_profit: float
    risk_amount: float  # USDT risked
    leverage: float


def calculate_trade_params(
    side: str,         # "long" or "short"
    entry_price: float,
    atr_value: float,
    account_balance: float,
    cfg: RiskConfig,
) -> TradeParams:
    """
    Compute position size and SL/TP from risk parameters.

    Position sizing:
      risk_amount = account_balance * risk_per_trade
      stop_distance = atr * sl_atr_mult
      qty = risk_amount / stop_distance   (in base coin units)

    Leverage is clamped to max_leverage.
    """
    if atr_value <= 0:
        raise ValueError(f"Invalid ATR value: {atr_value}")
    if entry_price <= 0:
        raise ValueError(f"Invalid entry price: {entry_price}")

    risk_amount = account_balance * cfg.risk_per_trade
    stop_distance = atr_value * cfg.sl_atr_mult
    tp_distance = atr_value * cfg.tp_atr_mult

    qty = risk_amount / stop_distance

    # Apply max position cap if set
    if cfg.max_position_qty > 0:
        qty = min(qty, cfg.max_position_qty)

    # Minimum viable qty guard
    qty = max(qty, 0.0)

    if side.lower() == "long":
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + tp_distance
    else:
        stop_loss = entry_price + stop_distance
        take_profit = entry_price - tp_distance

    # Implied leverage = notional / balance
    notional = qty * entry_price
    leverage = notional / account_balance if account_balance > 0 else 1.0
    leverage = min(leverage, cfg.max_leverage)

    return TradeParams(
        qty=round(qty, 4),
        stop_loss=round(stop_loss, 6),
        take_profit=round(take_profit, 6),
        risk_amount=round(risk_amount, 4),
        leverage=round(leverage, 2),
    )


def is_risk_acceptable(params: TradeParams, cfg: RiskConfig) -> bool:
    """Return True if the trade parameters are within risk limits."""
    if params.leverage > cfg.max_leverage:
        return False
    if params.qty <= 0:
        return False
    return True
