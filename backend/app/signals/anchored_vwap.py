"""Anchored VWAP — session anchor bounce / rejection scalp."""

from __future__ import annotations

import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.market_structure import swing_high_low
from app.signals.schemas import SetupResult, T1_R, T2_R

ANCHOR_LOOKBACK = 48


def _anchored_vwap(d: pd.DataFrame, anchor_idx: int) -> pd.Series:
    sub = d.iloc[anchor_idx:].copy()
    tp = (sub["high"] + sub["low"] + sub["close"]) / 3.0
    cum_v = sub["volume"].cumsum()
    cum_tpv = (tp * sub["volume"]).cumsum()
    return cum_tpv / cum_v.replace(0, pd.NA)


def _targets(entry: float, stop: float) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * T1_R, entry + sign * risk * T2_R]


def anchored_vwap(df: pd.DataFrame) -> SetupResult:
    """
    Anchor VWAP at session swing extreme:
    - Bull: anchor at swing low, buy AVWAP reclaim after dip
    - Bear: anchor at swing high, sell AVWAP rejection
    """
    name = "anchored_vwap"
    if len(df) < ANCHOR_LOOKBACK + 10:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    window = d.iloc[-ANCHOR_LOOKBACK:]
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    swing_high, swing_low = swing_high_low(d)
    atr_val = float(bar["atr_14"]) if not pd.isna(bar["atr_14"]) else 0.0

    bull_anchor = len(d) - ANCHOR_LOOKBACK + int(window["low"].values.argmin())
    bear_anchor = len(d) - ANCHOR_LOOKBACK + int(window["high"].values.argmax())

    av_bull = _anchored_vwap(d, bull_anchor)
    av_bear = _anchored_vwap(d, bear_anchor)
    if av_bull.empty or av_bear.empty:
        return SetupResult(setup_name=name, fired=False, reason="avwap unavailable")

    vwap_b = float(av_bull.iloc[-1])
    vwap_s = float(av_bear.iloc[-1])
    close = float(bar["close"])
    tol = max(atr_val * 0.25, close * 0.0015)

    dipped_avwap = float(bar["low"]) <= vwap_b + tol and float(prev["close"]) >= vwap_b - tol
    reclaim = close > vwap_b and close > float(prev["high"])
    vol_ok = float(bar["volume"]) > float(d["volume"].tail(20).mean()) * 1.15

    if dipped_avwap and reclaim and vol_ok and close > float(bar["open"]):
        entry = close
        stop = min(float(bar["low"]), swing_low) - max(atr_val * 0.35, close * 0.006)
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bullish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="anchored VWAP reclaim — dip & bounce from session anchor",
            sl_basis="avwap_swing_low",
            metadata={"volume_confirmed": vol_ok, "anchored_vwap": True},
        )

    tagged_avwap = float(bar["high"]) >= vwap_s - tol and float(prev["close"]) <= vwap_s + tol
    reject = close < vwap_s and close < float(prev["low"])

    if tagged_avwap and reject and vol_ok and close < float(bar["open"]):
        entry = close
        stop = max(float(bar["high"]), swing_high) + max(atr_val * 0.35, close * 0.006)
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bearish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="anchored VWAP rejection — tag & fail at session anchor",
            sl_basis="avwap_swing_high",
            metadata={"volume_confirmed": vol_ok, "anchored_vwap": True},
        )

    return SetupResult(setup_name=name, fired=False, reason="no AVWAP setup")
