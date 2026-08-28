"""Volume profile — POC / value area bounce scalp."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.market_structure import swing_high_low
from app.signals.schemas import SetupResult, T1_R, T2_R

LOOKBACK = 60
BINS = 24
VALUE_AREA_PCT = 0.70


def _profile_levels(d: pd.DataFrame) -> tuple[float, float, float] | None:
    """Return POC, VAL, VAH from volume-at-price histogram."""
    if len(d) < 20:
        return None
    low = float(d["low"].min())
    high = float(d["high"].max())
    if high <= low:
        return None

    edges = np.linspace(low, high, BINS + 1)
    vol_at = np.zeros(BINS)
    for _, row in d.iterrows():
        mid = (float(row["high"]) + float(row["low"])) / 2.0
        idx = min(BINS - 1, max(0, int((mid - low) / (high - low) * BINS)))
        vol_at[idx] += float(row["volume"])

    if vol_at.sum() <= 0:
        return None

    poc_idx = int(vol_at.argmax())
    poc = (edges[poc_idx] + edges[poc_idx + 1]) / 2.0

    order = np.argsort(vol_at)[::-1]
    cum = 0.0
    total = vol_at.sum()
    selected = []
    for i in order:
        cum += vol_at[i]
        selected.append(i)
        if cum / total >= VALUE_AREA_PCT:
            break
    val = (edges[min(selected)] + edges[min(selected) + 1]) / 2.0
    vah = (edges[max(selected)] + edges[max(selected) + 1]) / 2.0
    return poc, min(val, vah), max(val, vah)


def _targets(entry: float, stop: float) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * T1_R, entry + sign * risk * T2_R]


def volume_profile(df: pd.DataFrame) -> SetupResult:
    """
    Trade reactions at volume profile levels:
    - Long at VAL with rejection (target POC/VAH)
    - Short at VAH with rejection (target POC/VAL)
    """
    name = "volume_profile"
    if len(df) < LOOKBACK + 5:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    window = d.iloc[-LOOKBACK:]
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    levels = _profile_levels(window)
    if not levels:
        return SetupResult(setup_name=name, fired=False, reason="no profile")

    poc, val, vah = levels
    swing_high, swing_low = swing_high_low(d)
    atr_val = float(bar["atr_14"]) if not pd.isna(bar["atr_14"]) else 0.0
    close = float(bar["close"])
    tol = max(atr_val * 0.2, close * 0.0012)
    vol_ok = float(bar["volume"]) > float(window["volume"].mean()) * 1.2

    at_val = float(bar["low"]) <= val + tol and close > val
    bullish_reject = close > float(prev["close"]) and close > float(bar["open"])

    if at_val and bullish_reject and vol_ok and close < poc:
        entry = close
        stop = min(float(bar["low"]), swing_low, val) - max(atr_val * 0.35, close * 0.006)
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bullish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason=f"volume profile VAL bounce — POC {poc:.4g}",
            sl_basis="vp_val",
            metadata={"volume_confirmed": vol_ok, "poc": poc, "val": val, "vah": vah},
        )

    at_vah = float(bar["high"]) >= vah - tol and close < vah
    bearish_reject = close < float(prev["close"]) and close < float(bar["open"])

    if at_vah and bearish_reject and vol_ok and close > poc:
        entry = close
        stop = max(float(bar["high"]), swing_high, vah) + max(atr_val * 0.35, close * 0.006)
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bearish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason=f"volume profile VAH rejection — POC {poc:.4g}",
            sl_basis="vp_vah",
            metadata={"volume_confirmed": vol_ok, "poc": poc, "val": val, "vah": vah},
        )

    return SetupResult(setup_name=name, fired=False, reason="no VP level reaction")
