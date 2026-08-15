"""Confluence signal scoring and trade direction logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from bot.config import IndicatorConfig
from bot.regime import Regime


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass
class Signal:
    direction: Direction
    confluence: float      # 0.0 – 1.0
    reasons: list[str]


def _last(arr: np.ndarray) -> float:
    """Return last non-nan value."""
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return float("nan")
    return float(valid[-1])


def _prev(arr: np.ndarray) -> float:
    """Return second-to-last non-nan value."""
    valid = arr[~np.isnan(arr)]
    if len(valid) < 2:
        return float("nan")
    return float(valid[-2])


def score_signals(
    close: np.ndarray,
    volume: np.ndarray,
    indicators: dict[str, np.ndarray],
    regime: Regime,
    cfg: IndicatorConfig,
) -> Signal:
    """
    Score confluence for a LONG or SHORT entry on the latest bar.

    Scoring rubric (each sub-signal contributes 1 point):
    Long:
      1. ema_fast > ema_slow (bullish cross / alignment)
      2. close > ema_trend (above trend)
      3. RSI in oversold recovery  (rsi > oversold and rising)
      4. MACD histogram positive and rising
      5. close near/bouncing off lower Bollinger Band
      6. volume above its MA (confirmation)

    Short: mirror image.

    Max score = 6; confluence = score / 6.
    Regime filter: don't go against the trend.
    """
    reasons: list[str] = []

    ema_f = _last(indicators["ema_fast"])
    ema_s = _last(indicators["ema_slow"])
    ema_t = _last(indicators["ema_trend"])
    rsi_now = _last(indicators["rsi"])
    rsi_prev = _prev(indicators["rsi"])
    macd_h = _last(indicators["macd_hist"])
    macd_h_prev = _prev(indicators["macd_hist"])
    bb_upper = _last(indicators["bb_upper"])
    bb_lower = _last(indicators["bb_lower"])
    vol_now = _last(volume)
    vol_ma = _last(indicators["vol_ma"])
    price = _last(close)

    any_nan = any(
        np.isnan(x) for x in [ema_f, ema_s, ema_t, rsi_now, macd_h, bb_upper, bb_lower, vol_ma]
    )
    if any_nan:
        return Signal(Direction.NONE, 0.0, ["insufficient_data"])

    long_score = 0
    short_score = 0

    # 1. EMA alignment
    if ema_f > ema_s:
        long_score += 1
        reasons.append("ema_bullish")
    else:
        short_score += 1
        reasons.append("ema_bearish")

    # 2. Price vs trend EMA
    if price > ema_t:
        long_score += 1
        reasons.append("above_trend")
    else:
        short_score += 1
        reasons.append("below_trend")

    # 3. RSI
    if rsi_now > cfg.rsi_oversold and rsi_now > rsi_prev:
        long_score += 1
        reasons.append("rsi_long")
    if rsi_now < cfg.rsi_overbought and rsi_now < rsi_prev:
        short_score += 1
        reasons.append("rsi_short")

    # 4. MACD histogram
    if macd_h > 0 and macd_h > macd_h_prev:
        long_score += 1
        reasons.append("macd_long")
    if macd_h < 0 and macd_h < macd_h_prev:
        short_score += 1
        reasons.append("macd_short")

    # 5. Bollinger Band
    bb_range = bb_upper - bb_lower
    if bb_range > 0:
        bb_pos = (price - bb_lower) / bb_range
        if bb_pos < 0.30:
            long_score += 1
            reasons.append("bb_low")
        if bb_pos > 0.70:
            short_score += 1
            reasons.append("bb_high")

    # 6. Volume confirmation
    if vol_now > vol_ma:
        # Volume confirms whichever side is winning
        if long_score > short_score:
            long_score += 1
            reasons.append("vol_confirm_long")
        elif short_score > long_score:
            short_score += 1
            reasons.append("vol_confirm_short")

    total = 6
    # Regime filter
    if regime == Regime.TRENDING_DOWN and long_score > short_score:
        return Signal(Direction.NONE, long_score / total, reasons + ["regime_filter"])
    if regime == Regime.TRENDING_UP and short_score > long_score:
        return Signal(Direction.NONE, short_score / total, reasons + ["regime_filter"])

    if long_score > short_score:
        return Signal(Direction.LONG, long_score / total, reasons)
    elif short_score > long_score:
        return Signal(Direction.SHORT, short_score / total, reasons)
    else:
        return Signal(Direction.NONE, 0.0, reasons + ["tie"])
