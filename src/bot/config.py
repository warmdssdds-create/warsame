"""Configuration management – reads from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (silently ignored if absent)
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool = True) -> bool:
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ("1", "true", "yes")


def _env_float(key: str, default: float = 0.0) -> float:
    return float(os.environ.get(key, str(default)))


def _env_int(key: str, default: int = 0) -> int:
    return int(os.environ.get(key, str(default)))


@dataclass
class ExchangeConfig:
    api_key: str = field(default_factory=lambda: _env("BYBIT_API_KEY"))
    api_secret: str = field(default_factory=lambda: _env("BYBIT_API_SECRET"))
    # testnet=True by default – must explicitly opt-in to live trading
    testnet: bool = field(default_factory=lambda: _env_bool("BYBIT_TESTNET", True))
    # NOTE: Bybit linear perpetuals use category="linear" and
    #       the symbol naming convention is e.g. "ETCUSDT".
    symbol: str = field(default_factory=lambda: _env("SYMBOL", "ETCUSDT"))
    category: str = "linear"


@dataclass
class CandleConfig:
    interval: str = field(default_factory=lambda: _env("CANDLE_INTERVAL", "15"))
    """Bybit kline interval string: 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M"""
    lookback_bars: int = field(
        default_factory=lambda: _env_int("CANDLE_LOOKBACK_BARS", 500)
    )
    cache_dir: str = field(default_factory=lambda: _env("CANDLE_CACHE_DIR", "data"))


@dataclass
class IndicatorConfig:
    # EMA periods
    ema_fast: int = field(default_factory=lambda: _env_int("EMA_FAST", 9))
    ema_slow: int = field(default_factory=lambda: _env_int("EMA_SLOW", 21))
    ema_trend: int = field(default_factory=lambda: _env_int("EMA_TREND", 50))
    # RSI
    rsi_period: int = field(default_factory=lambda: _env_int("RSI_PERIOD", 14))
    rsi_oversold: float = field(
        default_factory=lambda: _env_float("RSI_OVERSOLD", 35.0)
    )
    rsi_overbought: float = field(
        default_factory=lambda: _env_float("RSI_OVERBOUGHT", 65.0)
    )
    # ATR
    atr_period: int = field(default_factory=lambda: _env_int("ATR_PERIOD", 14))
    # MACD
    macd_fast: int = field(default_factory=lambda: _env_int("MACD_FAST", 12))
    macd_slow: int = field(default_factory=lambda: _env_int("MACD_SLOW", 26))
    macd_signal: int = field(default_factory=lambda: _env_int("MACD_SIGNAL", 9))
    # Bollinger Bands
    bb_period: int = field(default_factory=lambda: _env_int("BB_PERIOD", 20))
    bb_std: float = field(default_factory=lambda: _env_float("BB_STD", 2.0))
    # Volume
    vol_ma_period: int = field(default_factory=lambda: _env_int("VOL_MA_PERIOD", 20))


@dataclass
class RegimeConfig:
    # ADX-like threshold to distinguish trending vs ranging
    adx_period: int = field(default_factory=lambda: _env_int("ADX_PERIOD", 14))
    adx_trending_threshold: float = field(
        default_factory=lambda: _env_float("ADX_TRENDING_THRESHOLD", 25.0)
    )


@dataclass
class RiskConfig:
    # Maximum fraction of account balance risked per trade
    risk_per_trade: float = field(
        default_factory=lambda: _env_float("RISK_PER_TRADE", 0.01)
    )
    # ATR multipliers for stop-loss and take-profit
    sl_atr_mult: float = field(
        default_factory=lambda: _env_float("SL_ATR_MULT", 2.0)
    )
    tp_atr_mult: float = field(
        default_factory=lambda: _env_float("TP_ATR_MULT", 3.0)
    )
    # Maximum leverage allowed
    max_leverage: float = field(
        default_factory=lambda: _env_float("MAX_LEVERAGE", 3.0)
    )
    # Minimum confluence score (0-1) required to enter a trade
    min_confluence: float = field(
        default_factory=lambda: _env_float("MIN_CONFLUENCE", 0.60)
    )
    # Maximum position size in contract units (0 = no limit besides risk)
    max_position_qty: float = field(
        default_factory=lambda: _env_float("MAX_POSITION_QTY", 0.0)
    )


@dataclass
class AlertConfig:
    telegram_bot_token: str = field(
        default_factory=lambda: _env("TELEGRAM_BOT_TOKEN")
    )
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID"))


@dataclass
class BotConfig:
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    candle: CandleConfig = field(default_factory=CandleConfig)
    indicator: IndicatorConfig = field(default_factory=IndicatorConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    alert: AlertConfig = field(default_factory=AlertConfig)
    # Seconds between main loop iterations
    loop_interval: int = field(
        default_factory=lambda: _env_int("LOOP_INTERVAL_SECONDS", 60)
    )
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", False))


def load_config() -> BotConfig:
    """Return a fully populated BotConfig from environment variables."""
    return BotConfig()
