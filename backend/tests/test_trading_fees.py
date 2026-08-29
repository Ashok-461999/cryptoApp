"""Tests for scalp fee + 1:2 TP pricing."""

from app.services.trading_fees import estimated_entry_drag_usdt, tp_price_from_rr


def test_tp_price_1_to_2_rr():
    entry = 2.414
    stop = 2.400  # ~0.58% SL distance
    t1, t2, gross, net = tp_price_from_rr(entry, stop, 1, 2.0, 21.27)
    assert t1 > entry
    assert t2 > t1
    assert gross > 0
    assert net < gross


def test_entry_drag_positive():
    drag = estimated_entry_drag_usdt(21.27)
    assert drag >= 0.08  # ~0.45% + fee on $21
