"""Setup functions for crypto futures — SMC scalp strategies."""

import pandas as pd

from app.signals.amd import amd_model
from app.signals.anchored_vwap import anchored_vwap
from app.signals.fibonacci import fibonacci_retrace
from app.signals.fvg import ifvg_reversal, liquidity_sweep
from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.market_structure import structure_fib_sweep
from app.signals.order_flow import order_flow
from app.signals.reversal import structure_reversal
from app.signals.schemas import SetupResult, T1_R, T2_R
from app.signals.supply_demand import supply_demand
from app.signals.volume_profile import volume_profile

ORB_BARS = 3
RANGE_LOOKBACK = 20


def _targets_from_r(entry: float, stop: float, r_multiples: tuple[float, ...] = (T1_R, T2_R)) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * m for m in r_multiples]


def orb_breakout(df: pd.DataFrame, orb_bars: int = ORB_BARS) -> SetupResult:
    name = "orb_breakout"
    if len(df) < orb_bars + 5:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    or_slice = d.iloc[:orb_bars]
    or_high = or_slice["high"].max()
    or_low = or_slice["low"].min()
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    vol_ok = bar["volume"] > bar.get("vol_sma_20", bar["volume"]) * 1.1

    if bar["close"] > or_high and prev["close"] <= or_high and vol_ok:
        entry = float(bar["close"])
        stop = float(or_low)
        return SetupResult(
            setup_name=name, fired=True, direction="bullish",
            entry=entry, stop_loss=stop, targets=_targets_from_r(entry, stop),
            reason="break above opening range", sl_basis="orb_boundary",
        )
    if bar["close"] < or_low and prev["close"] >= or_low and vol_ok:
        entry = float(bar["close"])
        stop = float(or_high)
        return SetupResult(
            setup_name=name, fired=True, direction="bearish",
            entry=entry, stop_loss=stop, targets=_targets_from_r(entry, stop),
            reason="break below opening range", sl_basis="orb_boundary",
        )
    return SetupResult(setup_name=name, fired=False, reason="no ORB trigger")


# Priority order: confluence & user-marked important strategies first
SETUP_FUNCTIONS = {
    "structure_fib_sweep": structure_fib_sweep,
    "liquidity_sweep": liquidity_sweep,
    "amd_model": amd_model,
    "ifvg_reversal": ifvg_reversal,
    "order_flow": order_flow,
    "anchored_vwap": anchored_vwap,
    "volume_profile": volume_profile,
    "supply_demand": supply_demand,
    # fvg_retest removed — poor live win rate, causes small losses
    "fibonacci_retrace": fibonacci_retrace,
    "structure_reversal": structure_reversal,
    "orb_breakout": orb_breakout,
}
