"""Market regime detection for crypto."""

from dataclasses import dataclass
from enum import Enum

import pandas as pd
import pandas_ta as ta

from app.signals.indicators import add_standard_indicators, atr


class Regime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"


SETUP_REGIME_MAP: dict[str, set[Regime]] = {
    "structure_fib_sweep": {Regime.TRENDING, Regime.VOLATILE, Regime.RANGING},
    "amd_model": {Regime.RANGING, Regime.VOLATILE, Regime.TRENDING},
    "liquidity_sweep": {Regime.TRENDING, Regime.VOLATILE, Regime.RANGING},
    "ifvg_reversal": {Regime.TRENDING, Regime.VOLATILE, Regime.RANGING},
    "order_flow": {Regime.TRENDING, Regime.VOLATILE, Regime.RANGING},
    "supply_demand": {Regime.RANGING, Regime.TRENDING, Regime.VOLATILE},
    "fibonacci_retrace": {Regime.TRENDING, Regime.RANGING},
    "structure_reversal": {Regime.TRENDING, Regime.VOLATILE, Regime.RANGING},
    "fvg_retest": {Regime.TRENDING, Regime.VOLATILE},
    "orb_breakout": {Regime.TRENDING, Regime.VOLATILE},
}


@dataclass
class RegimeSnapshot:
    regime: Regime
    adx: float
    atr_percentile: float
    trend_direction: str
    summary: str


def setup_allowed_in_regime(setup_name: str, regime: Regime) -> bool:
    return regime in SETUP_REGIME_MAP.get(setup_name, set())


def detect_regime(df: pd.DataFrame) -> RegimeSnapshot:
    d = add_standard_indicators(df)
    adx_result = ta.adx(d["high"], d["low"], d["close"], length=14)
    adx_val = 20.0
    if adx_result is not None and not adx_result.empty:
        col = [c for c in adx_result.columns if c.startswith("ADX")][0]
        v = adx_result[col].iloc[-1]
        adx_val = float(v) if not pd.isna(v) else 20.0

    atr_series = atr(d, 14)
    atr_hist = atr_series.dropna().tail(60)
    current_atr = float(atr_series.iloc[-1]) if not pd.isna(atr_series.iloc[-1]) else 0.0
    atr_pct = float((atr_hist < current_atr).sum() / len(atr_hist) * 100) if len(atr_hist) >= 10 else 50.0

    if adx_val >= 25:
        regime = Regime.TRENDING
        summary = f"Trending (ADX {adx_val:.0f})"
    elif atr_pct >= 70:
        regime = Regime.VOLATILE
        summary = f"Volatile (ATR pctl {atr_pct:.0f})"
    else:
        regime = Regime.RANGING
        summary = f"Ranging (ADX {adx_val:.0f})"

    recent = d.tail(8)
    trend = "neutral"
    if len(recent) >= 8:
        hh = recent["high"].iloc[-1] > recent["high"].iloc[-4]
        ll = recent["low"].iloc[-1] < recent["low"].iloc[-4]
        if hh and not ll:
            trend = "bullish"
        elif ll and not hh:
            trend = "bearish"

    return RegimeSnapshot(regime=regime, adx=adx_val, atr_percentile=atr_pct, trend_direction=trend, summary=summary)
