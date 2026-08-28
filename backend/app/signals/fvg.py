"""Fair Value Gap (FVG) detection and liquidity sweep setups."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.schemas import SetupResult, T1_R, T2_R


@dataclass
class FvgZone:
    kind: str
    top: float
    bottom: float
    bar_index: int

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0

    @property
    def size(self) -> float:
        return abs(self.top - self.bottom)


def find_fvg_zones(df: pd.DataFrame, lookback: int = 40) -> list[FvgZone]:
    d = ensure_ohlcv(df)
    zones: list[FvgZone] = []
    start = max(2, len(d) - lookback)
    for i in range(start, len(d)):
        c0 = d.iloc[i - 2]
        c2 = d.iloc[i]
        if float(c0["high"]) < float(c2["low"]):
            zones.append(FvgZone(kind="bullish", top=float(c2["low"]), bottom=float(c0["high"]), bar_index=i))
        if float(c0["low"]) > float(c2["high"]):
            zones.append(FvgZone(kind="bearish", top=float(c0["low"]), bottom=float(c2["high"]), bar_index=i))
    return zones


def _buf_pct(price: float, zone_size: float) -> float:
    return max(zone_size * 0.15, price * 0.001)


def fvg_retest(df: pd.DataFrame) -> SetupResult:
    name = "fvg_retest"
    if len(df) < 25:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = ensure_ohlcv(df)
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    zones = find_fvg_zones(d)
    if not zones:
        return SetupResult(setup_name=name, fired=False, reason="no FVG zones")

    for zone in reversed(zones[-6:]):
        buf = _buf_pct(float(bar["close"]), zone.size)
        if zone.kind == "bullish":
            touched = float(bar["low"]) <= zone.top and float(prev["low"]) <= zone.top
            rejected = float(bar["close"]) > zone.mid and float(bar["close"]) > float(prev["close"])
            if touched and rejected and zone.size >= zone.mid * 0.0001:
                entry = float(bar["close"])
                stop = zone.bottom - buf
                risk = entry - stop
                if risk <= 0:
                    continue
                return SetupResult(
                    setup_name=name, fired=True, direction="bullish",
                    entry=entry, stop_loss=stop,
                    targets=[entry + risk * T1_R, entry + risk * T2_R],
                    reason="bullish FVG retest", sl_basis="fvg_edge",
                    metadata={"volume_confirmed": True, "fvg": True},
                )
        if zone.kind == "bearish":
            touched = float(bar["high"]) >= zone.bottom and float(prev["high"]) >= zone.bottom
            rejected = float(bar["close"]) < zone.mid and float(bar["close"]) < float(prev["close"])
            if touched and rejected and zone.size >= zone.mid * 0.0001:
                entry = float(bar["close"])
                stop = zone.top + buf
                risk = stop - entry
                if risk <= 0:
                    continue
                return SetupResult(
                    setup_name=name, fired=True, direction="bearish",
                    entry=entry, stop_loss=stop,
                    targets=[entry - risk * T1_R, entry - risk * T2_R],
                    reason="bearish FVG retest", sl_basis="fvg_edge",
                    metadata={"volume_confirmed": True, "fvg": True},
                )
    return SetupResult(setup_name=name, fired=False, reason="no FVG retest")


def liquidity_sweep(df: pd.DataFrame, swing: int = 14) -> SetupResult:
    name = "liquidity_sweep"
    if len(df) < swing + 8:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    window = d.iloc[-(swing + 1) : -1]
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())
    range_size = max(swing_high - swing_low, float(bar["close"]) * 0.001)

    body = abs(float(bar["close"]) - float(bar["open"]))
    full_range = float(bar["high"]) - float(bar["low"])
    if full_range <= 0:
        return SetupResult(setup_name=name, fired=False, reason="flat bar")

    displacement = body / full_range >= 0.38
    vol_ok = float(bar["volume"]) > float(window["volume"].mean()) * 1.15
    if not displacement or not vol_ok:
        return SetupResult(setup_name=name, fired=False, reason="no sweep displacement")

    meta = {"displacement": True, "volume_confirmed": vol_ok}

    if (
        float(bar["high"]) > swing_high
        and float(bar["close"]) < swing_high
        and float(bar["close"]) < float(prev["low"])
    ):
        entry = float(bar["close"])
        stop = float(bar["high"]) + range_size * 0.08
        risk = stop - entry
        if risk > 0:
            return SetupResult(
                setup_name=name,
                fired=True,
                direction="bearish",
                entry=entry,
                stop_loss=stop,
                targets=[entry - risk * T1_R, entry - risk * T2_R],
                reason="liquidity sweep above highs — CHoCH down",
                sl_basis="swing_high",
                metadata={**meta, "structure_break": True},
            )

    if (
        float(bar["low"]) < swing_low
        and float(bar["close"]) > swing_low
        and float(bar["close"]) > float(prev["high"])
    ):
        entry = float(bar["close"])
        stop = float(bar["low"]) - range_size * 0.08
        risk = entry - stop
        if risk > 0:
            return SetupResult(
                setup_name=name,
                fired=True,
                direction="bullish",
                entry=entry,
                stop_loss=stop,
                targets=[entry + risk * T1_R, entry + risk * T2_R],
                reason="liquidity sweep below lows — CHoCH up",
                sl_basis="swing_low",
                metadata={**meta, "structure_break": True},
            )
    return SetupResult(setup_name=name, fired=False, reason="no liquidity sweep")


def ifvg_reversal(df: pd.DataFrame, lookback: int = 50) -> SetupResult:
    """
    Inverse FVG (IFVG): gap gets violated then flips role (support/resistance).
    Bullish IFVG: bearish FVG broken upward → retest from above.
    Bearish IFVG: bullish FVG broken downward → retest from below.
    """
    name = "ifvg_reversal"
    if len(df) < 25:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    zones = find_fvg_zones(d, lookback=lookback)
    if not zones:
        return SetupResult(setup_name=name, fired=False, reason="no FVG zones")

    vol_ok = float(bar["volume"]) > float(d["volume"].tail(20).mean()) * 1.15
    buf = _buf_pct(float(bar["close"]), zones[-1].size if zones else float(bar["close"]) * 0.001)

    for zone in reversed(zones[-8:]):
        if zone.kind == "bearish":
            # Inverted to support: price closed above bearish FVG top, now retesting
            broke_up = float(d.iloc[zone.bar_index :]["close"].max()) > zone.top
            retest = float(bar["low"]) <= zone.top + buf and float(bar["close"]) > zone.top
            rejection = float(bar["close"]) > float(bar["open"]) and float(bar["close"]) > float(prev["close"])
            if broke_up and retest and rejection and vol_ok:
                entry = float(bar["close"])
                stop = zone.bottom - buf
                risk = entry - stop
                if risk > 0:
                    return SetupResult(
                        setup_name=name,
                        fired=True,
                        direction="bullish",
                        entry=entry,
                        stop_loss=stop,
                        targets=[entry + risk * T1_R, entry + risk * T2_R],
                        reason="bullish IFVG — inverted gap support",
                        sl_basis="ifvg_support",
                        metadata={"ifvg": True, "volume_confirmed": vol_ok, "original_fvg": "bearish"},
                    )

        if zone.kind == "bullish":
            broke_down = float(d.iloc[zone.bar_index :]["close"].min()) < zone.bottom
            retest = float(bar["high"]) >= zone.bottom - buf and float(bar["close"]) < zone.bottom
            rejection = float(bar["close"]) < float(bar["open"]) and float(bar["close"]) < float(prev["close"])
            if broke_down and retest and rejection and vol_ok:
                entry = float(bar["close"])
                stop = zone.top + buf
                risk = stop - entry
                if risk > 0:
                    return SetupResult(
                        setup_name=name,
                        fired=True,
                        direction="bearish",
                        entry=entry,
                        stop_loss=stop,
                        targets=[entry - risk * T1_R, entry - risk * T2_R],
                        reason="bearish IFVG — inverted gap resistance",
                        sl_basis="ifvg_resistance",
                        metadata={"ifvg": True, "volume_confirmed": vol_ok, "original_fvg": "bullish"},
                    )

    return SetupResult(setup_name=name, fired=False, reason="no IFVG retest")
