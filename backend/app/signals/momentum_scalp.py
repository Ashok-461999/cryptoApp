"""Pure momentum scalp — 1m movement + 24h direction, no SMC strategy required."""

from __future__ import annotations

import pandas as pd

from app.signals.indicators import ensure_ohlcv
from app.signals.schemas import SetupResult, T1_R

MIN_MOM_1M_PCT = 0.15
MIN_VOL_SPIKE = 1.08


def momentum_scalp(df: pd.DataFrame, change_24h_pct: float = 0.0) -> SetupResult:
    """Fire when short-term price movement aligns with 24h mover direction."""
    name = "momentum_scalp"
    if len(df) < 8:
        return SetupResult(setup_name=name, fired=False, reason="insufficient 1m bars")

    d = ensure_ohlcv(df)
    bar = d.iloc[-1]
    entry = float(bar["close"])
    if entry <= 0:
        return SetupResult(setup_name=name, fired=False, reason="no price")

    look = d.tail(5)
    mom_5 = (float(look["close"].iloc[-1]) - float(look["close"].iloc[0])) / float(look["close"].iloc[0]) * 100
    body = float(bar["close"]) - float(bar["open"])
    body_pct = abs(body) / entry * 100
    vol = float(bar["volume"])
    avg_vol = float(d["volume"].tail(20).mean()) if len(d) >= 20 else vol

    bullish = mom_5 > MIN_MOM_1M_PCT and body > 0 and change_24h_pct > 0
    bearish = mom_5 < -MIN_MOM_1M_PCT and body < 0 and change_24h_pct < 0

    if not bullish and not bearish:
        return SetupResult(setup_name=name, fired=False, reason="no aligned momentum")

    if body_pct < 0.04:
        return SetupResult(setup_name=name, fired=False, reason="candle body too small")
    if vol < avg_vol * MIN_VOL_SPIKE:
        return SetupResult(setup_name=name, fired=False, reason="volume not confirming")

    if bullish:
        stop = float(look["low"].min()) - entry * 0.0003
        if stop >= entry:
            stop = entry * (1 - 0.0025)
        risk = entry - stop
        if risk <= 0:
            return SetupResult(setup_name=name, fired=False, reason="invalid stop")
        targets = [entry + risk * T1_R, entry + risk * (T1_R + 0.3)]
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bullish",
            entry=entry,
            stop_loss=stop,
            targets=targets,
            reason=f"1m momentum +{mom_5:.2f}% · 24h {change_24h_pct:+.1f}%",
            sl_basis="1m_swing_tight",
            metadata={"momentum_pct": mom_5, "volume_confirmed": True},
        )

    stop = float(look["high"].max()) + entry * 0.0003
    if stop <= entry:
        stop = entry * (1 + 0.0025)
    risk = stop - entry
    if risk <= 0:
        return SetupResult(setup_name=name, fired=False, reason="invalid stop")
    targets = [entry - risk * T1_R, entry - risk * (T1_R + 0.3)]
    return SetupResult(
        setup_name=name,
        fired=True,
        direction="bearish",
        entry=entry,
        stop_loss=stop,
        targets=targets,
        reason=f"1m momentum {mom_5:.2f}% · 24h {change_24h_pct:+.1f}%",
        sl_basis="1m_swing_tight",
        metadata={"momentum_pct": mom_5, "volume_confirmed": True},
    )
