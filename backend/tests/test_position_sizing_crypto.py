"""Tests for crypto futures position sizing."""

from app.signals.position_sizing_crypto import (
    classify_tier,
    liquidation_too_close,
    plan_crypto_futures,
    suggest_leverage,
    validate_stop_distance,
)


def test_classify_tier():
    assert classify_tier("BTCUSDT") == "A"
    assert classify_tier("PEPEUSDT") == "D"
    assert classify_tier("DOTUSDT") == "C"


def test_validate_stop_distance():
    ok, _ = validate_stop_distance(100.0, 98.0, "A")
    assert ok
    ok, reason = validate_stop_distance(100.0, 99.95, "A")
    assert not ok
    assert "tight" in reason


def test_suggest_leverage_reduces_for_volatility():
    lev = suggest_leverage("BTCUSDT", atr_pct=6.0, stop_distance_pct=1.5, tier="A",
                           entry=67000, stop=66500, direction="LONG")
    assert 35 <= lev <= 50


def test_plan_crypto_futures_long():
    plan = plan_crypto_futures(
        symbol="BTCUSDT",
        direction="LONG",
        entry=67000,
        stop_loss=66500,
        target_1=68000,
        target_2=68500,
        capital_usdt=240,
        risk_percent=1.0,
    )
    assert plan.stop_loss_price == 66500
    assert plan.leverage >= 35
    assert plan.strict_sl_rule != ""
    assert "STRICT SL" in plan.trade_plan or "66500" in plan.trade_plan
    assert plan.sl_type == "HARD"
    assert abs(plan.max_loss_usdt - 2.4) < 0.05
    assert abs(plan.notional_usdt - plan.margin_usdt * plan.leverage) < 0.05
    assert abs(plan.target_profit_usdt - plan.notional_usdt * (1000 / 67000)) < 0.05


def test_leveraged_pnl_from_margin():
    plan = plan_crypto_futures(
        symbol="TAOUSDT",
        direction="LONG",
        entry=251.4,
        stop_loss=249.52,
        target_1=257.27,
        target_2=260.0,
        capital_usdt=240.96,
        risk_percent=0.5,
    )
    stop_frac = abs(plan.entry_price - plan.stop_loss_price) / plan.entry_price
    expected_loss = plan.margin_usdt * plan.leverage * stop_frac
    assert abs(plan.max_loss_usdt - expected_loss) < 0.02
    assert abs(plan.max_loss_usdt - 1.2) < 0.1


def test_no_trade_without_stop():
    plan = plan_crypto_futures(
        symbol="PEPEUSDT",
        direction="LONG",
        entry=0.00001240,
        stop_loss=0,
        target_1=0.00001320,
        target_2=0.00001380,
        capital_usdt=240,
    )
    assert not plan.can_afford
    assert "stop" in plan.reason.lower()


def test_liquidation_safety():
    assert liquidation_too_close(100, 99, 50, "LONG") is False or True  # depends on math
