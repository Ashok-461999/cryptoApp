"""Tests for buy-dip / sell-top scalp logic."""

import pandas as pd

from app.signals.momentum_scalp import DIP_ZONE, TOP_ZONE, _buy_dip, _range_context, _sell_top, dip_top_scalp
from app.signals.scalp_levels import build_scalp_targets, validate_scalp_levels


def _df_from_rows(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _make_ohlcv_series(base_rows: list[dict], count: int = 14) -> pd.DataFrame:
    """Pad to LOOKBACK+2 bars."""
    rows = list(base_rows)
    while len(rows) < count:
        rows.insert(0, dict(rows[0]))
    return _df_from_rows(rows)


def test_buy_dip_only_in_low_zone():
    lows = [95.0] * 13 + [95.5]
    highs = [105.0] * 13 + [96.5]
    closes = [100.0] * 13 + [96.0]
    rows = [{"open": c, "high": h, "low": l, "close": c, "volume": 1000}
            for c, h, l in zip(closes, highs, lows)]
    rows[-1] = {"open": 96.2, "high": 96.8, "low": 95.5, "close": 96.4, "volume": 2000}
    ctx = _range_context(_df_from_rows(rows))
    assert ctx is not None
    assert ctx["position"] <= DIP_ZONE
    res = _buy_dip(ctx, 5.0)
    assert res.fired
    assert res.direction == "bullish"
    assert res.stop_loss < res.entry
    assert res.targets[0] > res.entry


def test_sell_top_only_in_high_zone():
    lows = [95.0] * 13 + [103.5]
    highs = [105.0] * 13 + [104.5]
    closes = [100.0] * 13 + [104.0]
    rows = [{"open": c, "high": h, "low": l, "close": c, "volume": 1000}
            for c, h, l in zip(closes, highs, lows)]
    rows[-1] = {"open": 104.2, "high": 104.5, "low": 103.8, "close": 103.9, "volume": 2000}
    ctx = _range_context(_df_from_rows(rows))
    assert ctx is not None
    assert ctx["position"] >= TOP_ZONE
    res = _sell_top(ctx, 5.0)
    assert res.fired
    assert res.direction == "bearish"
    assert res.stop_loss > res.entry
    assert res.targets[0] < res.entry


def test_no_buy_at_range_top():
    lows = [98.0] * 15
    highs = [102.0] * 15
    closes = [101.5] * 15
    rows = [{"open": c, "high": h, "low": l, "close": c, "volume": 1000}
            for c, h, l in zip(closes, highs, lows)]
    ctx = _range_context(_df_from_rows(rows))
    assert ctx is not None
    assert ctx["position"] > DIP_ZONE
    assert not _buy_dip(ctx, 5.0).fired


def test_scalp_targets_valid():
    entry, stop = 100.0, 99.5
    out = build_scalp_targets(entry, stop, "LONG", 1.0, 40.0)
    assert out is not None
    t1, t2, _, _ = out
    assert validate_scalp_levels(entry, stop, t1, "LONG")
    out_s = build_scalp_targets(100.0, 100.5, "SHORT", 2.0, 40.0)
    assert out_s is not None
    assert validate_scalp_levels(100.0, 100.5, out_s[0], "SHORT")
