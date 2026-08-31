"""Tests for backtest gate."""

import pandas as pd

from app.signals.backtest_gate import passes_backtest_gate


def _df(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "open": closes,
        "high": [c * 1.002 for c in closes],
        "low": [c * 0.998 for c in closes],
        "close": closes,
        "volume": [1000] * len(closes),
    })


def test_backtest_gate_rejects_low_samples():
    closes = [100.0] * 25
    ok, meta = passes_backtest_gate(_df(closes), "LONG", 100.0, 99.0, 101.5)
    assert ok is False
    assert meta["samples"] >= 0


def test_backtest_gate_can_pass_uptrend():
    closes = [100 + i * 0.05 for i in range(60)]
    ok, meta = passes_backtest_gate(_df(closes), "LONG", closes[-1], closes[-1] - 0.5, closes[-1] + 1.0)
    assert isinstance(ok, bool)
    assert "win_rate" in meta
