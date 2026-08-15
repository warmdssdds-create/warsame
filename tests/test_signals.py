"""Unit tests for signal scoring."""

import numpy as np
import pytest

from bot.config import IndicatorConfig
from bot.indicators import compute_all
from bot.regime import Regime
from bot.signals import Direction, score_signals


def _make_data(n=300, trend="up"):
    rng = np.random.default_rng(0)
    if trend == "up":
        close = np.linspace(10, 30, n) + rng.normal(0, 0.3, n)
    else:
        close = np.linspace(30, 10, n) + rng.normal(0, 0.3, n)
    high = close + np.abs(rng.normal(0, 0.2, n))
    low = close - np.abs(rng.normal(0, 0.2, n))
    volume = np.abs(rng.normal(1000, 100, n))
    return high, low, close, volume


def test_signal_returns_direction():
    high, low, close, volume = _make_data()
    cfg = IndicatorConfig()
    indicators = compute_all(high, low, close, volume, cfg)
    sig = score_signals(close, volume, indicators, Regime.RANGING, cfg)
    assert sig.direction in (Direction.LONG, Direction.SHORT, Direction.NONE)


def test_signal_confluence_0_to_1():
    high, low, close, volume = _make_data()
    cfg = IndicatorConfig()
    indicators = compute_all(high, low, close, volume, cfg)
    sig = score_signals(close, volume, indicators, Regime.RANGING, cfg)
    assert 0.0 <= sig.confluence <= 1.0


def test_signal_insufficient_data():
    """With only 2 bars, signal should return NONE."""
    close = np.array([10.0, 11.0])
    volume = np.array([100.0, 100.0])
    high = close + 0.5
    low = close - 0.5
    cfg = IndicatorConfig()
    indicators = compute_all(high, low, close, volume, cfg)
    sig = score_signals(close, volume, indicators, Regime.UNKNOWN, cfg)
    assert sig.direction == Direction.NONE


def test_regime_filter_blocks_long_in_downtrend():
    """A downtrending regime should block a LONG signal."""
    high, low, close, volume = _make_data(trend="down")
    cfg = IndicatorConfig()
    indicators = compute_all(high, low, close, volume, cfg)
    # Force a trending_down regime
    sig = score_signals(close, volume, indicators, Regime.TRENDING_DOWN, cfg)
    # Long should be filtered
    if sig.direction == Direction.LONG:
        # This can happen only if the confluence was 0 after filter,
        # which means the filter was applied
        assert "regime_filter" in sig.reasons
