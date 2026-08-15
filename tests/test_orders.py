"""Unit tests for order execution helpers (mocked session)."""

import pytest
from unittest.mock import MagicMock, patch

from bot.config import BotConfig, ExchangeConfig
from bot.orders import open_position, close_position, check_and_exit_conditions
from bot.risk import TradeParams
from bot.signals import Direction


def _cfg(dry_run=False) -> BotConfig:
    cfg = BotConfig()
    cfg.exchange = ExchangeConfig(api_key="k", api_secret="s", testnet=True)
    cfg.dry_run = dry_run
    return cfg


def _params() -> TradeParams:
    return TradeParams(qty=1.0, stop_loss=19.0, take_profit=23.0, risk_amount=10.0, leverage=2.0)


# -------------------------------------------------------------------------
# dry-run mode
# -------------------------------------------------------------------------

def test_open_position_dry_run_returns_none():
    cfg = _cfg(dry_run=True)
    result = open_position(MagicMock(), cfg, Direction.LONG, _params())
    assert result is None


def test_close_position_dry_run_returns_none():
    cfg = _cfg(dry_run=True)
    pos = {"size": "1", "side": "Buy"}
    result = close_position(MagicMock(), cfg, pos)
    assert result is None


# -------------------------------------------------------------------------
# live mode (mocked exchange)
# -------------------------------------------------------------------------

def test_open_position_calls_place_order():
    cfg = _cfg(dry_run=False)
    session = MagicMock()

    with patch("bot.orders.set_leverage") as mock_lev, \
         patch("bot.orders.place_order", return_value={"orderId": "123"}) as mock_order:
        result = open_position(session, cfg, Direction.LONG, _params())

    mock_order.assert_called_once()
    assert result["orderId"] == "123"


def test_close_position_calls_place_order():
    cfg = _cfg(dry_run=False)
    session = MagicMock()
    pos = {"size": "2.5", "side": "Buy"}

    with patch("bot.orders.place_order", return_value={"orderId": "456"}) as mock_order:
        result = close_position(session, cfg, pos)

    mock_order.assert_called_once()
    call_kwargs = mock_order.call_args
    assert call_kwargs.kwargs.get("reduce_only") is True
    assert call_kwargs.kwargs.get("side") == "Sell"


def test_close_position_zero_size_returns_none():
    cfg = _cfg(dry_run=False)
    pos = {"size": "0", "side": "Buy"}
    result = close_position(MagicMock(), cfg, pos)
    assert result is None


# -------------------------------------------------------------------------
# Exit conditions
# -------------------------------------------------------------------------

def test_check_exit_no_position():
    assert check_and_exit_conditions(MagicMock(), _cfg(), None, Direction.LONG) is False


def test_check_exit_signal_flip_long_to_short():
    pos = {"side": "Buy"}
    assert check_and_exit_conditions(MagicMock(), _cfg(), pos, Direction.SHORT) is True


def test_check_exit_no_flip():
    pos = {"side": "Buy"}
    assert check_and_exit_conditions(MagicMock(), _cfg(), pos, Direction.LONG) is False
