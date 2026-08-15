"""Event-driven backtest engine.

Reuses the same indicator, regime, signal, and risk modules as the live bot.
Feed historical candles one-by-one to simulate bar-close signal generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import structlog

from bot.candles import Candle, candles_to_arrays
from bot.config import BotConfig
from bot.indicators import compute_all
from bot.regime import detect_regime
from bot.risk import TradeParams, calculate_trade_params, is_risk_acceptable
from bot.signals import Direction, score_signals

log = structlog.get_logger(__name__)


@dataclass
class Trade:
    entry_bar: int
    direction: Direction
    entry_price: float
    qty: float
    stop_loss: float
    take_profit: float
    exit_bar: Optional[int] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    exit_reason: str = ""


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    initial_balance: float = 0.0

    @property
    def final_balance(self) -> float:
        return self.equity_curve[-1] if self.equity_curve else self.initial_balance

    @property
    def total_pnl(self) -> float:
        return self.final_balance - self.initial_balance

    @property
    def win_rate(self) -> float:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return 0.0
        winners = sum(1 for t in closed if (t.pnl or 0) > 0)
        return winners / len(closed)

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for v in self.equity_curve:
            peak = max(peak, v)
            dd = (peak - v) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    def summary(self) -> dict:
        closed = [t for t in self.trades if t.pnl is not None]
        return {
            "initial_balance": self.initial_balance,
            "final_balance": round(self.final_balance, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_trades": len(closed),
            "win_rate": round(self.win_rate, 4),
            "max_drawdown": round(self.max_drawdown, 4),
        }


def run_backtest(
    candles: list[Candle],
    cfg: BotConfig,
    initial_balance: float = 10_000.0,
) -> BacktestResult:
    """
    Iterate through candles bar-by-bar.

    On each bar:
      - compute indicators on the window up to (and including) this bar
      - score signals
      - check exits for open trade
      - check entries if flat

    NOTE: All orders are filled at the *open* of the next bar (bar+1)
    to avoid look-ahead bias.
    """
    min_bars = max(cfg.indicator.ema_trend, cfg.indicator.bb_period, cfg.indicator.rsi_period) + 30
    result = BacktestResult(initial_balance=initial_balance)
    balance = initial_balance
    result.equity_curve.append(balance)

    open_trade: Optional[Trade] = None

    for i in range(min_bars, len(candles) - 1):
        window = candles[: i + 1]
        arr = candles_to_arrays(window)
        high = arr["high"]
        low = arr["low"]
        close = arr["close"]
        volume = arr["volume"]

        indicators = compute_all(high, low, close, volume, cfg.indicator)
        regime = detect_regime(high, low, close, cfg.regime)
        signal = score_signals(close, volume, indicators, regime, cfg.indicator)

        next_bar = candles[i + 1]
        fill_price = next_bar.open  # execution at next open

        # --- Check exit for open trade ---
        if open_trade is not None:
            exit_price, exit_reason = _check_exit(open_trade, next_bar, signal)
            if exit_price is not None:
                pnl = _calc_pnl(open_trade, exit_price)
                balance += pnl
                open_trade.exit_bar = i + 1
                open_trade.exit_price = exit_price
                open_trade.pnl = pnl
                open_trade.exit_reason = exit_reason
                log.debug(
                    "trade_closed",
                    bar=i,
                    pnl=round(pnl, 4),
                    reason=exit_reason,
                )
                open_trade = None

        # --- Check entry ---
        if open_trade is None and signal.direction != Direction.NONE:
            if signal.confluence >= cfg.risk.min_confluence:
                atr_val = float(indicators["atr"][-1])
                if not np.isnan(atr_val) and atr_val > 0 and balance > 0:
                    params = calculate_trade_params(
                        side=signal.direction.value,
                        entry_price=fill_price,
                        atr_value=atr_val,
                        account_balance=balance,
                        cfg=cfg.risk,
                    )
                    if is_risk_acceptable(params, cfg.risk):
                        open_trade = Trade(
                            entry_bar=i + 1,
                            direction=signal.direction,
                            entry_price=fill_price,
                            qty=params.qty,
                            stop_loss=params.stop_loss,
                            take_profit=params.take_profit,
                        )
                        result.trades.append(open_trade)

        result.equity_curve.append(balance)

    # Force-close any open trade at the last bar
    if open_trade is not None:
        last = candles[-1]
        pnl = _calc_pnl(open_trade, last.close)
        balance += pnl
        open_trade.exit_bar = len(candles) - 1
        open_trade.exit_price = last.close
        open_trade.pnl = pnl
        open_trade.exit_reason = "end_of_data"
        result.equity_curve.append(balance)

    return result


def _check_exit(
    trade: Trade,
    bar: Candle,
    signal,
) -> tuple[float | None, str]:
    """Return (exit_price, reason) or (None, '')."""
    # SL/TP hit (within bar range)
    if trade.direction == Direction.LONG:
        if bar.low <= trade.stop_loss:
            return trade.stop_loss, "stop_loss"
        if bar.high >= trade.take_profit:
            return trade.take_profit, "take_profit"
        # Signal flip
        if signal.direction == Direction.SHORT:
            return bar.open, "signal_flip"
    else:
        if bar.high >= trade.stop_loss:
            return trade.stop_loss, "stop_loss"
        if bar.low <= trade.take_profit:
            return trade.take_profit, "take_profit"
        if signal.direction == Direction.LONG:
            return bar.open, "signal_flip"
    return None, ""


def _calc_pnl(trade: Trade, exit_price: float) -> float:
    if trade.direction == Direction.LONG:
        return trade.qty * (exit_price - trade.entry_price)
    else:
        return trade.qty * (trade.entry_price - exit_price)
