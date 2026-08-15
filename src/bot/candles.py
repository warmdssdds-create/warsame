"""Historical candle management: backfill, caching, incremental updates."""

from __future__ import annotations

import csv
import os
import time
from pathlib import Path
from typing import NamedTuple

import numpy as np
import structlog
from pybit.unified_trading import HTTP

from bot.config import CandleConfig, ExchangeConfig
from bot.exchange import fetch_klines

log = structlog.get_logger(__name__)

CANDLE_FIELDS = ("timestamp", "open", "high", "low", "close", "volume", "turnover")


class Candle(NamedTuple):
    timestamp: int   # epoch milliseconds
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float


def _cache_path(cache_dir: str, symbol: str, interval: str) -> Path:
    p = Path(cache_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{symbol}_{interval}.csv"


def _load_cache(path: Path) -> list[Candle]:
    if not path.exists():
        return []
    candles: list[Candle] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append(
                Candle(
                    timestamp=int(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    turnover=float(row["turnover"]),
                )
            )
    return candles


def _save_cache(path: Path, candles: list[Candle]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CANDLE_FIELDS)
        writer.writeheader()
        for c in candles:
            writer.writerow(c._asdict())


def _interval_ms(interval: str) -> int:
    """Return interval duration in milliseconds."""
    mapping = {
        "1": 60_000,
        "3": 180_000,
        "5": 300_000,
        "15": 900_000,
        "30": 1_800_000,
        "60": 3_600_000,
        "120": 7_200_000,
        "240": 14_400_000,
        "360": 21_600_000,
        "720": 43_200_000,
        "D": 86_400_000,
        "W": 604_800_000,
        "M": 2_592_000_000,
    }
    return mapping.get(interval, 900_000)


def backfill(
    session: HTTP,
    symbol: str,
    interval: str,
    lookback_bars: int,
    category: str = "linear",
    cache_dir: str = "data",
) -> list[Candle]:
    """Fetch enough bars to satisfy *lookback_bars*, using local cache."""
    cache_path = _cache_path(cache_dir, symbol, interval)
    cached = _load_cache(cache_path)

    now_ms = int(time.time() * 1000)
    needed_start_ms = now_ms - lookback_bars * _interval_ms(interval)

    # Determine oldest needed timestamp from cache
    if cached and cached[0].timestamp <= needed_start_ms and cached[-1].timestamp >= needed_start_ms:
        # Cache already covers enough history; just fetch recent bars
        fetch_start = cached[-1].timestamp + 1
    else:
        cached = []
        fetch_start = needed_start_ms

    # Fetch in pages of 200 bars
    all_new: list[Candle] = []
    page_start = fetch_start
    while page_start < now_ms:
        rows = fetch_klines(
            session,
            symbol=symbol,
            interval=interval,
            category=category,
            limit=200,
            start=page_start,
        )
        if not rows:
            break
        for row in rows:
            ts = int(row[0])
            if ts < page_start:
                continue
            all_new.append(
                Candle(
                    timestamp=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    turnover=float(row[6]),
                )
            )
        last_ts = int(rows[-1][0])
        if last_ts <= page_start:
            break
        page_start = last_ts + 1
        time.sleep(0.1)  # gentle rate-limiting

    # Merge and de-duplicate (keep latest version of each timestamp)
    merged: dict[int, Candle] = {c.timestamp: c for c in cached}
    for c in all_new:
        merged[c.timestamp] = c

    result = sorted(merged.values(), key=lambda c: c.timestamp)

    # Trim to lookback
    if len(result) > lookback_bars:
        result = result[-lookback_bars:]

    _save_cache(cache_path, result)
    log.info("candles_ready", symbol=symbol, interval=interval, count=len(result))
    return result


def candles_to_arrays(candles: list[Candle]) -> dict[str, np.ndarray]:
    """Convert list of Candle to dict of numpy arrays."""
    return {
        "timestamp": np.array([c.timestamp for c in candles], dtype=np.int64),
        "open": np.array([c.open for c in candles], dtype=np.float64),
        "high": np.array([c.high for c in candles], dtype=np.float64),
        "low": np.array([c.low for c in candles], dtype=np.float64),
        "close": np.array([c.close for c in candles], dtype=np.float64),
        "volume": np.array([c.volume for c in candles], dtype=np.float64),
    }


def append_candle(candles: list[Candle], new: Candle) -> list[Candle]:
    """Append or update the latest candle (same-bar update from websocket)."""
    if candles and candles[-1].timestamp == new.timestamp:
        return candles[:-1] + [new]
    return candles + [new]
