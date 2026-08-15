# Warsame ETCUSDT Bybit Trading Bot

A production-ready algorithmic trading bot for the **ETCUSDT** perpetual futures market on Bybit, written in Python 3.11+.

## Features

- **Bybit REST + WebSocket** connectivity via `pybit`
- **Historical candle backfill** with local CSV caching
- **Technical indicators**: EMA, RSI, ATR, MACD, Bollinger Bands, ADX (pure numpy)
- **Market regime detection**: trending (up/down) vs ranging via ADX
- **Confluence scoring**: multi-factor signal aggregation (0–1 score)
- **Risk management**: ATR-based position sizing, SL/TP calculation, leverage cap
- **Order execution**: market orders with SL/TP attached, reduce-only exits
- **Position reconciliation**: live vs local state diff with warnings
- **Alerting**: optional Telegram notifications
- **Graceful shutdown**: SIGINT/SIGTERM handled
- **Backtesting**: event-driven engine reusing live strategy code
- **Testnet-first**: requires explicit opt-in to go live

## Project Structure

```
src/
  bot/
    config.py       – environment-based configuration
    logger.py       – structlog setup
    exchange.py     – Bybit REST helpers with tenacity retry
    candles.py      – backfill, CSV cache, array conversion
    indicators.py   – EMA, SMA, RSI, ATR, MACD, BB, ADX
    regime.py       – market regime detection
    signals.py      – confluence scoring
    risk.py         – position sizing & SL/TP
    orders.py       – order execution
    reconcile.py    – position reconciliation
    alerts.py       – Telegram alerting
    runner.py       – main loop
    main.py         – entry point
  backtest/
    engine.py       – event-driven backtest engine
    main.py         – CLI entry point
tests/
  test_indicators.py
  test_signals.py
  test_risk.py
  test_orders.py
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
# Edit .env with your Bybit testnet API key/secret
```

### 3. Run the bot (testnet)

```bash
python -m bot.main
```

### 4. Run backtest

```bash
# Fetch data first (runs briefly to populate cache), then:
python -m backtest.main --source live --balance 10000
# Or use existing cache:
python -m backtest.main --source cache
```

### 5. Run tests

```bash
pytest
```

## Configuration

All settings are read from environment variables (or `.env`). See `.env.example` for the full list.

| Variable | Default | Description |
|---|---|---|
| `BYBIT_TESTNET` | `true` | Use testnet (**must** set to `false` for live) |
| `SYMBOL` | `ETCUSDT` | Trading symbol |
| `CANDLE_INTERVAL` | `15` | Kline interval (minutes string) |
| `RISK_PER_TRADE` | `0.01` | Fraction of balance risked per trade |
| `SL_ATR_MULT` | `2.0` | ATR multiplier for stop-loss |
| `TP_ATR_MULT` | `3.0` | ATR multiplier for take-profit |
| `MAX_LEVERAGE` | `3.0` | Maximum leverage |
| `MIN_CONFLUENCE` | `0.60` | Minimum signal score to enter |
| `DRY_RUN` | `false` | Log orders but don't send to exchange |
| `LOOP_INTERVAL_SECONDS` | `60` | Seconds between ticks |

## Design Assumptions

- **Single symbol, single position**: The bot manages one ETCUSDT position at a time.
- **Market orders only**: SL/TP are attached to the entry order via Bybit's conditional fields.
- **Exchange-managed SL/TP**: The exchange handles SL/TP triggers; the bot places market entries and monitors for signal flips.
- **Bybit linear perpetuals**: Uses `category=linear` throughout. `ETCUSDT` is the standard Bybit linear perpetual ticker.
- **Testnet by default**: Live trading requires `BYBIT_TESTNET=false` explicitly.

## Warning

Algorithmic trading carries significant financial risk. This software is provided for educational purposes. Always test thoroughly on testnet before risking real capital.