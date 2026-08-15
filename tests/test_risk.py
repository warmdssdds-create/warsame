"""Unit tests for risk management."""

import pytest
from bot.config import RiskConfig
from bot.risk import TradeParams, calculate_trade_params, is_risk_acceptable


def _cfg(**kwargs) -> RiskConfig:
    return RiskConfig(**kwargs)


def test_long_sl_below_entry():
    cfg = _cfg()
    params = calculate_trade_params("long", 20.0, 1.0, 1000.0, cfg)
    assert params.stop_loss < 20.0
    assert params.take_profit > 20.0


def test_short_sl_above_entry():
    cfg = _cfg()
    params = calculate_trade_params("short", 20.0, 1.0, 1000.0, cfg)
    assert params.stop_loss > 20.0
    assert params.take_profit < 20.0


def test_risk_amount_is_correct_fraction():
    cfg = _cfg(risk_per_trade=0.02)
    params = calculate_trade_params("long", 20.0, 0.5, 5000.0, cfg)
    # risk = 5000 * 0.02 = 100; stop_dist = 0.5 * 2 = 1.0; qty = 100
    assert params.risk_amount == pytest.approx(100.0)


def test_qty_capped_by_max():
    cfg = _cfg(max_position_qty=1.0)
    params = calculate_trade_params("long", 20.0, 0.01, 100_000.0, cfg)
    assert params.qty <= 1.0


def test_invalid_atr_raises():
    cfg = _cfg()
    with pytest.raises(ValueError):
        calculate_trade_params("long", 20.0, 0.0, 1000.0, cfg)


def test_invalid_price_raises():
    cfg = _cfg()
    with pytest.raises(ValueError):
        calculate_trade_params("long", 0.0, 1.0, 1000.0, cfg)


def test_is_risk_acceptable_true():
    params = TradeParams(qty=1.0, stop_loss=19.0, take_profit=23.0, risk_amount=10.0, leverage=1.5)
    cfg = _cfg(max_leverage=3.0)
    assert is_risk_acceptable(params, cfg)


def test_is_risk_acceptable_false_leverage():
    params = TradeParams(qty=1.0, stop_loss=19.0, take_profit=23.0, risk_amount=10.0, leverage=5.0)
    cfg = _cfg(max_leverage=3.0)
    assert not is_risk_acceptable(params, cfg)


def test_is_risk_acceptable_false_zero_qty():
    params = TradeParams(qty=0.0, stop_loss=19.0, take_profit=23.0, risk_amount=0.0, leverage=1.0)
    cfg = _cfg()
    assert not is_risk_acceptable(params, cfg)
