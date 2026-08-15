"""Bybit exchange connectivity: REST + WebSocket helpers."""

from __future__ import annotations

import time
from typing import Any

import structlog
from pybit.unified_trading import HTTP, WebSocket
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.config import ExchangeConfig

log = structlog.get_logger(__name__)


def build_http_session(cfg: ExchangeConfig) -> HTTP:
    """Create a pybit HTTP session (testnet or mainnet)."""
    return HTTP(
        testnet=cfg.testnet,
        api_key=cfg.api_key,
        api_secret=cfg.api_secret,
    )


def build_ws_session(
    cfg: ExchangeConfig,
    on_message: Any,
    channel_type: str = "linear",
) -> WebSocket:
    """Create a pybit WebSocket session."""
    return WebSocket(
        testnet=cfg.testnet,
        channel_type=channel_type,
        on_message=on_message,
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def fetch_klines(
    session: HTTP,
    symbol: str,
    interval: str,
    category: str = "linear",
    limit: int = 200,
    start: int | None = None,
    end: int | None = None,
) -> list[list]:
    """Fetch OHLCV klines with retry.

    Returns list of [timestamp_ms, open, high, low, close, volume, turnover]
    sorted oldest-first (Bybit returns newest-first).
    """
    kwargs: dict[str, Any] = {
        "category": category,
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }
    if start is not None:
        kwargs["start"] = start
    if end is not None:
        kwargs["end"] = end

    resp = session.get_kline(**kwargs)
    if resp.get("retCode") != 0:
        raise RuntimeError(f"Bybit kline error: {resp}")

    rows = resp["result"]["list"]
    # Bybit returns newest first; reverse for chronological order
    return list(reversed(rows))


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def fetch_account_balance(session: HTTP, coin: str = "USDT") -> float:
    """Return available wallet balance for *coin* on the unified account."""
    resp = session.get_wallet_balance(accountType="UNIFIED", coin=coin)
    if resp.get("retCode") != 0:
        raise RuntimeError(f"Bybit balance error: {resp}")
    accounts = resp["result"]["list"]
    for account in accounts:
        for asset in account.get("coin", []):
            if asset["coin"] == coin:
                return float(asset["availableToWithdraw"])
    return 0.0


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def fetch_position(
    session: HTTP, symbol: str, category: str = "linear"
) -> dict | None:
    """Return the open position dict for *symbol*, or None if flat."""
    resp = session.get_positions(category=category, symbol=symbol)
    if resp.get("retCode") != 0:
        raise RuntimeError(f"Bybit positions error: {resp}")
    positions = resp["result"]["list"]
    for pos in positions:
        if pos["symbol"] == symbol and float(pos.get("size", 0)) != 0:
            return pos
    return None


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def place_order(
    session: HTTP,
    symbol: str,
    side: str,
    qty: float,
    order_type: str = "Market",
    category: str = "linear",
    stop_loss: float | None = None,
    take_profit: float | None = None,
    reduce_only: bool = False,
) -> dict:
    """Place a market order with optional SL/TP.

    NOTE: Bybit linear perpetuals require qty in contract base units
    (e.g. ETC for ETCUSDT).  The caller is responsible for correct sizing.
    """
    kwargs: dict[str, Any] = {
        "category": category,
        "symbol": symbol,
        "side": side,  # "Buy" or "Sell"
        "orderType": order_type,
        "qty": str(qty),
        "timeInForce": "IOC",
        "reduceOnly": reduce_only,
    }
    if stop_loss is not None:
        kwargs["stopLoss"] = str(stop_loss)
    if take_profit is not None:
        kwargs["takeProfit"] = str(take_profit)

    resp = session.place_order(**kwargs)
    if resp.get("retCode") != 0:
        raise RuntimeError(f"Bybit place_order error: {resp}")
    log.info("order_placed", symbol=symbol, side=side, qty=qty, resp=resp["result"])
    return resp["result"]


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def set_leverage(
    session: HTTP, symbol: str, leverage: float, category: str = "linear"
) -> None:
    """Set cross-margin leverage for *symbol*."""
    resp = session.set_leverage(
        category=category,
        symbol=symbol,
        buyLeverage=str(leverage),
        sellLeverage=str(leverage),
    )
    # retCode 110043 means leverage unchanged – treat as success
    if resp.get("retCode") not in (0, 110043):
        raise RuntimeError(f"Bybit set_leverage error: {resp}")


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)
def fetch_ticker(
    session: HTTP, symbol: str, category: str = "linear"
) -> dict:
    """Return the latest ticker dict for *symbol*."""
    resp = session.get_tickers(category=category, symbol=symbol)
    if resp.get("retCode") != 0:
        raise RuntimeError(f"Bybit ticker error: {resp}")
    return resp["result"]["list"][0]
