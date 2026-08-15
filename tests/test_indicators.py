"""Unit tests for indicator calculations."""

import numpy as np
import pytest

from bot.indicators import ema, sma, rsi, atr, macd, bollinger_bands, volume_ma, adx


def _close(n=100, seed=42):
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.normal(0, 1, n)) + 30.0


def _hlc(n=100, seed=42):
    close = _close(n, seed)
    high = close + np.abs(np.random.default_rng(seed).normal(0, 0.5, n))
    low = close - np.abs(np.random.default_rng(seed + 1).normal(0, 0.5, n))
    return high, low, close


# -------------------------------------------------------------------------
# EMA
# -------------------------------------------------------------------------

def test_ema_length():
    c = _close()
    result = ema(c, 9)
    assert len(result) == len(c)


def test_ema_first_nans():
    c = _close(50)
    result = ema(c, 9)
    assert np.all(np.isnan(result[:8]))
    assert not np.isnan(result[8])


def test_ema_period_1_equals_price():
    c = _close(20)
    result = ema(c, 1)
    np.testing.assert_array_almost_equal(result, c)


def test_ema_too_short():
    with pytest.raises(ValueError):
        ema(np.array([1.0, 2.0]), 10)


# -------------------------------------------------------------------------
# SMA
# -------------------------------------------------------------------------

def test_sma_rolling():
    c = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    result = sma(c, 3)
    assert np.isnan(result[0])
    assert np.isnan(result[1])
    assert result[2] == pytest.approx(2.0)
    assert result[4] == pytest.approx(4.0)


# -------------------------------------------------------------------------
# RSI
# -------------------------------------------------------------------------

def test_rsi_range():
    c = _close(200)
    result = rsi(c, 14)
    valid = result[~np.isnan(result)]
    assert np.all(valid >= 0)
    assert np.all(valid <= 100)


def test_rsi_length():
    c = _close(100)
    result = rsi(c, 14)
    assert len(result) == len(c)


# -------------------------------------------------------------------------
# ATR
# -------------------------------------------------------------------------

def test_atr_non_negative():
    h, l, c = _hlc(100)
    result = atr(h, l, c, 14)
    valid = result[~np.isnan(result)]
    assert np.all(valid >= 0)


def test_atr_length():
    h, l, c = _hlc(100)
    result = atr(h, l, c, 14)
    assert len(result) == len(c)


# -------------------------------------------------------------------------
# MACD
# -------------------------------------------------------------------------

def test_macd_returns_three_arrays():
    c = _close(200)
    m, s, h = macd(c, 12, 26, 9)
    assert len(m) == len(c)
    assert len(s) == len(c)
    assert len(h) == len(c)


def test_macd_histogram_equals_diff():
    c = _close(200)
    m, s, h = macd(c)
    valid = ~np.isnan(m) & ~np.isnan(s)
    np.testing.assert_array_almost_equal(h[valid], (m - s)[valid])


# -------------------------------------------------------------------------
# Bollinger Bands
# -------------------------------------------------------------------------

def test_bb_upper_above_lower():
    c = _close(100)
    upper, mid, lower = bollinger_bands(c, 20, 2.0)
    valid = ~np.isnan(upper)
    assert np.all(upper[valid] >= lower[valid])


def test_bb_mid_is_sma():
    c = _close(100)
    _, mid, _ = bollinger_bands(c, 20, 2.0)
    ref = sma(c, 20)
    valid = ~np.isnan(mid)
    np.testing.assert_array_almost_equal(mid[valid], ref[valid])


# -------------------------------------------------------------------------
# ADX
# -------------------------------------------------------------------------

def test_adx_non_negative():
    h, l, c = _hlc(200)
    adx_arr, plus_di, minus_di = adx(h, l, c, 14)
    valid = adx_arr[~np.isnan(adx_arr)]
    assert np.all(valid >= 0)


def test_adx_length():
    h, l, c = _hlc(200)
    adx_arr, _, _ = adx(h, l, c, 14)
    assert len(adx_arr) == len(c)
