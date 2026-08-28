"""AMD model — Accumulation, Manipulation, Distribution (ICT/SMC scalp)."""

import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.schemas import SetupResult

ACCUM_BARS = 18
MANIP_WICK_RATIO = 0.55
MIN_DISPLACEMENT = 0.45
VOL_MULT = 1.25


def _targets_scalp(entry: float, stop: float, r_multiples: tuple[float, ...] = (4.0, 6.0)) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * m for m in r_multiples]


def amd_model(df: pd.DataFrame) -> SetupResult:
    """
    AMD scalp:
    1. Accumulation — tight range (range < 1.0 ATR)
    2. Manipulation — wick sweeps range edge (liquidity grab)
    3. Distribution — displacement close back through range mid + volume
    """
    name = "amd_model"
    if len(df) < ACCUM_BARS + 8:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    accum = d.iloc[-(ACCUM_BARS + 1) : -1]
    bar = d.iloc[-1]
    prev = d.iloc[-2]

    range_high = float(accum["high"].max())
    range_low = float(accum["low"].min())
    range_width = range_high - range_low
    atr_val = float(bar["atr_14"]) if not pd.isna(bar["atr_14"]) else range_width
    mid = (range_high + range_low) / 2

    if range_width <= 0:
        return SetupResult(setup_name=name, fired=False, reason="invalid range")

    if range_width > 1.0 * atr_val:
        return SetupResult(setup_name=name, fired=False, reason="not accumulating")

    vol_ok = float(bar["volume"]) > float(accum["volume"].mean()) * VOL_MULT
    body = abs(float(bar["close"]) - float(bar["open"]))
    full_range = float(bar["high"]) - float(bar["low"])
    if full_range <= 0:
        return SetupResult(setup_name=name, fired=False, reason="no range on bar")

    displacement = body / full_range >= MIN_DISPLACEMENT
    if not displacement or not vol_ok:
        return SetupResult(setup_name=name, fired=False, reason="no distribution impulse")

    meta_base = {
        "phase": "distribution",
        "range_high": range_high,
        "range_low": range_low,
        "displacement": True,
        "volume_confirmed": vol_ok,
    }

    lower_wick = (
        float(bar["close"]) - float(bar["low"])
        if float(bar["close"]) >= float(bar["open"])
        else float(bar["open"]) - float(bar["low"])
    )
    swept_low = float(bar["low"]) < range_low and float(prev["low"]) >= range_low
    if (
        swept_low
        and float(bar["close"]) > mid
        and float(bar["close"]) > float(prev["high"])
        and lower_wick / full_range >= MANIP_WICK_RATIO
    ):
        entry = float(bar["close"])
        stop = float(bar["low"]) - atr_val * 0.12
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bullish",
            entry=entry,
            stop_loss=stop,
            targets=_targets_scalp(entry, stop),
            reason="bullish AMD — sweep lows then distribute up",
            sl_basis="manipulation_wick",
            metadata={**meta_base, "structure_break": True},
        )

    upper_wick = (
        float(bar["high"]) - float(bar["close"])
        if float(bar["close"]) <= float(bar["open"])
        else float(bar["high"]) - float(bar["open"])
    )
    swept_high = float(bar["high"]) > range_high and float(prev["high"]) <= range_high
    if (
        swept_high
        and float(bar["close"]) < mid
        and float(bar["close"]) < float(prev["low"])
        and upper_wick / full_range >= MANIP_WICK_RATIO
    ):
        entry = float(bar["close"])
        stop = float(bar["high"]) + atr_val * 0.12
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bearish",
            entry=entry,
            stop_loss=stop,
            targets=_targets_scalp(entry, stop),
            reason="bearish AMD — sweep highs then distribute down",
            sl_basis="manipulation_wick",
            metadata={**meta_base, "structure_break": True},
        )

    return SetupResult(setup_name=name, fired=False, reason="no AMD distribution")
