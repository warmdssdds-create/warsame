"""Backtest entry point: python -m backtest.main"""

from __future__ import annotations

import argparse
import json
import sys

from bot.candles import Candle, _cache_path, _load_cache
from bot.config import load_config
from bot.exchange import build_http_session, fetch_klines
from bot.logger import setup_logging
from backtest.engine import run_backtest


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Warsame backtest runner")
    parser.add_argument("--balance", type=float, default=10_000.0, help="Initial balance in USDT")
    parser.add_argument(
        "--source",
        choices=["cache", "live"],
        default="cache",
        help="Use cached CSV data or fetch fresh from Bybit",
    )
    args = parser.parse_args()

    cfg = load_config()

    if args.source == "live":
        from bot.candles import backfill
        session = build_http_session(cfg.exchange)
        candles = backfill(
            session,
            symbol=cfg.exchange.symbol,
            interval=cfg.candle.interval,
            lookback_bars=cfg.candle.lookback_bars,
            category=cfg.exchange.category,
            cache_dir=cfg.candle.cache_dir,
        )
    else:
        path = _cache_path(cfg.candle.cache_dir, cfg.exchange.symbol, cfg.candle.interval)
        candles = _load_cache(path)
        if not candles:
            print(f"No cached data at {path}. Run with --source live first.", file=sys.stderr)
            sys.exit(1)

    result = run_backtest(candles, cfg, initial_balance=args.balance)
    summary = result.summary()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
