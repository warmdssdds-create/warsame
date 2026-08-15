"""Main bot runner: event loop, WebSocket feed, strategy orchestration."""

from __future__ import annotations

import signal
import sys
import time

import structlog

from bot.alerts import send_alert
from bot.candles import Candle, append_candle, backfill, candles_to_arrays
from bot.config import BotConfig, load_config
from bot.exchange import build_http_session, fetch_account_balance, fetch_ticker
from bot.indicators import compute_all
from bot.logger import setup_logging
from bot.orders import check_and_exit_conditions, close_position, open_position
from bot.reconcile import reconcile_position
from bot.regime import detect_regime
from bot.risk import calculate_trade_params, is_risk_acceptable
from bot.signals import Direction, score_signals

log = structlog.get_logger(__name__)

_RUNNING = True


def _shutdown(sig, frame):  # noqa: ANN001
    global _RUNNING
    log.info("shutdown_requested", signal=sig)
    _RUNNING = False


def run(cfg: BotConfig) -> None:
    """Main trading loop."""
    global _RUNNING

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    session = build_http_session(cfg.exchange)

    log.info(
        "bot_starting",
        symbol=cfg.exchange.symbol,
        testnet=cfg.exchange.testnet,
        dry_run=cfg.dry_run,
    )
    send_alert(
        cfg.alert,
        f"🤖 Bot starting: {cfg.exchange.symbol} testnet={cfg.exchange.testnet}",
    )

    # --- Backfill historical candles ---
    candles = backfill(
        session,
        symbol=cfg.exchange.symbol,
        interval=cfg.candle.interval,
        lookback_bars=cfg.candle.lookback_bars,
        category=cfg.exchange.category,
        cache_dir=cfg.candle.cache_dir,
    )

    local_side: str | None = None  # "Buy", "Sell", or None

    while _RUNNING:
        try:
            _tick(session, cfg, candles, local_side)
        except Exception as exc:
            log.error("tick_error", exc=str(exc), exc_info=True)
            send_alert(cfg.alert, f"⚠️ Tick error: {exc}")

        # Sleep until next bar
        time.sleep(cfg.loop_interval)

    log.info("bot_stopped")
    send_alert(cfg.alert, "🛑 Bot stopped.")


def _tick(
    session,
    cfg: BotConfig,
    candles: list[Candle],
    local_side: str | None,
) -> None:
    # 1. Fetch latest candle / refresh last bar
    ticker = fetch_ticker(session, cfg.exchange.symbol, cfg.exchange.category)
    last_price = float(ticker["lastPrice"])

    # Append a synthetic "current" candle from ticker for signal scoring
    # (full candles are refreshed via backfill at startup)
    if candles:
        last_ts = candles[-1].timestamp
        arr = candles_to_arrays(candles)
        high = arr["high"]
        low = arr["low"]
        close = arr["close"]
        volume = arr["volume"]
    else:
        log.warning("no_candles")
        return

    # 2. Compute indicators
    indicators = compute_all(high, low, close, volume, cfg.indicator)

    # 3. Detect regime
    regime = detect_regime(high, low, close, cfg.regime)

    # 4. Score signals
    signal = score_signals(close, volume, indicators, regime, cfg.indicator)

    log.info(
        "signal",
        direction=signal.direction,
        confluence=signal.confluence,
        regime=regime,
        price=last_price,
        reasons=signal.reasons,
    )

    # 5. Reconcile position
    live_pos = reconcile_position(session, cfg.exchange, local_side)
    local_side = live_pos.get("side") if live_pos else None

    # 6. Exit logic
    if live_pos and check_and_exit_conditions(session, cfg, live_pos, signal.direction):
        close_result = close_position(session, cfg, live_pos)
        if close_result:
            send_alert(cfg.alert, f"📤 Position closed: {cfg.exchange.symbol}")
        local_side = None
        live_pos = None

    # 7. Entry logic
    if live_pos is None and signal.direction != Direction.NONE:
        if signal.confluence >= cfg.risk.min_confluence:
            balance = fetch_account_balance(session)
            atr_val = float(indicators["atr"][-1]) if not __import__("numpy").isnan(indicators["atr"][-1]) else None
            if atr_val and atr_val > 0 and balance > 0:
                params = calculate_trade_params(
                    side=signal.direction.value,
                    entry_price=last_price,
                    atr_value=atr_val,
                    account_balance=balance,
                    cfg=cfg.risk,
                )
                if is_risk_acceptable(params, cfg.risk):
                    result = open_position(session, cfg, signal.direction, params)
                    if result:
                        local_side = "Buy" if signal.direction == Direction.LONG else "Sell"
                        send_alert(
                            cfg.alert,
                            f"📥 Opened {signal.direction.value} {params.qty} "
                            f"{cfg.exchange.symbol} @ ~{last_price}  "
                            f"SL={params.stop_loss} TP={params.take_profit}",
                        )
