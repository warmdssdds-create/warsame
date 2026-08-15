"""Market regime detection: trending vs ranging."""

from __future__ import annotations

from enum import Enum

import numpy as np

from bot.config import RegimeConfig
from bot.indicators import adx


class Regime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    UNKNOWN = "unknown"


def detect_regime(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    cfg: RegimeConfig,
) -> Regime:
    """Classify the current market regime using ADX and DI lines."""
    if len(close) < cfg.adx_period * 2 + 2:
        return Regime.UNKNOWN

    adx_arr, plus_di, minus_di = adx(high, low, close, cfg.adx_period)

    # Use last valid value
    last_adx = _last_valid(adx_arr)
    last_plus_di = _last_valid(plus_di)
    last_minus_di = _last_valid(minus_di)

    if last_adx is None:
        return Regime.UNKNOWN

    if last_adx >= cfg.adx_trending_threshold:
        if last_plus_di > last_minus_di:
            return Regime.TRENDING_UP
        else:
            return Regime.TRENDING_DOWN
    return Regime.RANGING


def _last_valid(arr: np.ndarray) -> float | None:
    valid = arr[~np.isnan(arr)]
    return float(valid[-1]) if len(valid) > 0 else None
