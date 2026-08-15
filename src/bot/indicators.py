"""Technical indicator calculations using pure numpy."""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _check_min(arr: np.ndarray, min_len: int, name: str) -> None:
    if len(arr) < min_len:
        raise ValueError(f"{name} requires at least {min_len} bars, got {len(arr)}")


# ---------------------------------------------------------------------------
# Moving averages
# ---------------------------------------------------------------------------

def ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average."""
    _check_min(values, period, "ema")
    result = np.full_like(values, np.nan)
    k = 2.0 / (period + 1)
    # Seed with simple average of first *period* values
    result[period - 1] = np.mean(values[:period])
    for i in range(period, len(values)):
        result[i] = values[i] * k + result[i - 1] * (1 - k)
    return result


def sma(values: np.ndarray, period: int) -> np.ndarray:
    """Simple moving average."""
    _check_min(values, period, "sma")
    result = np.full_like(values, np.nan)
    for i in range(period - 1, len(values)):
        result[i] = np.mean(values[i - period + 1 : i + 1])
    return result


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder RSI."""
    _check_min(close, period + 1, "rsi")
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    avg_gain = np.full(len(close), np.nan)
    avg_loss = np.full(len(close), np.nan)

    avg_gain[period] = np.mean(gain[:period])
    avg_loss[period] = np.mean(loss[:period])

    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gain[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + loss[i - 1]) / period

    rs = np.where(avg_loss == 0, np.inf, avg_gain / avg_loss)
    result = 100.0 - (100.0 / (1.0 + rs))
    result[:period] = np.nan
    return result


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Average True Range (Wilder smoothing)."""
    _check_min(close, period + 1, "atr")
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    tr = np.maximum(
        high - low,
        np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)),
    )

    result = np.full(len(close), np.nan)
    result[period] = np.mean(tr[1 : period + 1])
    for i in range(period + 1, len(close)):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period
    return result


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------

def macd(
    close: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD line, signal line, histogram."""
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    macd_line = fast_ema - slow_ema

    # Compute signal only over valid (non-nan) portion
    valid_start = slow - 1
    sig_line = np.full_like(macd_line, np.nan)
    if len(macd_line) - valid_start >= signal:
        sig_values = ema(macd_line[valid_start:], signal)
        sig_line[valid_start:] = sig_values

    histogram = macd_line - sig_line
    return macd_line, sig_line, histogram


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def bollinger_bands(
    close: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (upper, middle, lower)."""
    middle = sma(close, period)
    rolling_std = np.full_like(close, np.nan)
    for i in range(period - 1, len(close)):
        rolling_std[i] = np.std(close[i - period + 1 : i + 1], ddof=0)
    upper = middle + std_dev * rolling_std
    lower = middle - std_dev * rolling_std
    return upper, middle, lower


# ---------------------------------------------------------------------------
# Volume MA
# ---------------------------------------------------------------------------

def volume_ma(volume: np.ndarray, period: int = 20) -> np.ndarray:
    return sma(volume, period)


# ---------------------------------------------------------------------------
# ADX (for regime detection)
# ---------------------------------------------------------------------------

def adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns (ADX, +DI, -DI) arrays."""
    _check_min(close, period * 2 + 1, "adx")
    n = len(close)
    atr_arr = atr(high, low, close, period)

    up_move = np.diff(high)
    down_move = -np.diff(low)

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # Wilder smoothing for DM
    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)
    smooth_plus = np.full(n, np.nan)
    smooth_minus = np.full(n, np.nan)

    smooth_plus[period] = np.sum(plus_dm[:period])
    smooth_minus[period] = np.sum(minus_dm[:period])

    for i in range(period + 1, n):
        smooth_plus[i] = smooth_plus[i - 1] - smooth_plus[i - 1] / period + plus_dm[i - 1]
        smooth_minus[i] = smooth_minus[i - 1] - smooth_minus[i - 1] / period + minus_dm[i - 1]

    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = np.where(atr_arr != 0, 100 * smooth_plus / atr_arr, 0.0)
        minus_di = np.where(atr_arr != 0, 100 * smooth_minus / atr_arr, 0.0)

    dx = np.full(n, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        di_sum = plus_di + minus_di
        di_diff = np.abs(plus_di - minus_di)
        dx = np.where(di_sum != 0, 100 * di_diff / di_sum, 0.0)

    adx_arr = np.full(n, np.nan)
    # First ADX value is SMA of DX
    start = period * 2
    if start < n:
        adx_arr[start] = np.nanmean(dx[period:start + 1])
        for i in range(start + 1, n):
            adx_arr[i] = (adx_arr[i - 1] * (period - 1) + dx[i]) / period

    return adx_arr, plus_di, minus_di


# ---------------------------------------------------------------------------
# Convenience: compute all indicators at once
# ---------------------------------------------------------------------------

def compute_all(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    cfg: "IndicatorConfig",  # noqa: F821  (forward ref)
) -> dict[str, np.ndarray]:
    from bot.config import IndicatorConfig  # local import to avoid circular

    nan = np.full_like(close, np.nan)

    def _try(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError:
            return nan.copy()

    ema_fast = _try(ema, close, cfg.ema_fast)
    ema_slow = _try(ema, close, cfg.ema_slow)
    ema_trend = _try(ema, close, cfg.ema_trend)
    rsi_arr = _try(rsi, close, cfg.rsi_period)
    atr_arr = _try(atr, high, low, close, cfg.atr_period)

    try:
        macd_line, macd_sig, macd_hist = macd(close, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)
    except ValueError:
        macd_line = macd_sig = macd_hist = nan.copy()

    try:
        bb_upper, bb_mid, bb_lower = bollinger_bands(close, cfg.bb_period, cfg.bb_std)
    except ValueError:
        bb_upper = bb_mid = bb_lower = nan.copy()

    vol_ma_arr = _try(volume_ma, volume, cfg.vol_ma_period)

    return {
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "ema_trend": ema_trend,
        "rsi": rsi_arr,
        "atr": atr_arr,
        "macd": macd_line,
        "macd_signal": macd_sig,
        "macd_hist": macd_hist,
        "bb_upper": bb_upper,
        "bb_mid": bb_mid,
        "bb_lower": bb_lower,
        "vol_ma": vol_ma_arr,
    }
