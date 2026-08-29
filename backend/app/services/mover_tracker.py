"""Mover / meme coin trade levels — Entry, SL, TP1 refreshed every 10–15 min with entry time."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services.crypto_futures_client import futures_client
from app.services.crypto_watchlist import WatchlistSymbol
from app.signals.crypto_scanner import crypto_scanner
from app.signals.indicators import atr_pct
from app.signals.market_structure import swing_high_low
from app.signals.regime import detect_regime
from app.signals.schemas import T1_R
from app.signals.momentum_scalp import momentum_scalp
from app.signals.sl_levels import normalize_stop_loss
from app.signals.trade_decision import SETUP_PRIORITY, evaluate_trade_decision

logger = logging.getLogger(__name__)

_cache: dict[str, dict] = {}

_SETUP_LABELS = {
    "momentum_scalp": "Momentum Scalp",
    "order_flow": "Order Flow",
    "liquidity_sweep": "Liquidity Sweep",
    "anchored_vwap": "Anchored VWAP",
    "volume_profile": "Volume Profile",
    "ifvg_reversal": "IFVG",
    "structure_fib_sweep": "Structure+Fib",
    "amd_model": "AMD Model",
    "supply_demand": "Supply & Demand",
    "fibonacci_retrace": "Fibonacci",
    "structure_reversal": "Structure Reversal",
}


def _ttl_minutes() -> int:
    return max(10, min(15, get_settings().mover_levels_refresh_minutes))


def _cache_valid(symbol: str, force: bool) -> bool:
    if force:
        return False
    row = _cache.get(symbol.upper())
    if not row:
        return False
    at = row.get("cached_at")
    if not isinstance(at, datetime):
        return False
    return datetime.now(timezone.utc) - at < timedelta(minutes=_ttl_minutes())


def _best_setup(symbol: str, df, regime, category: str, change_24h: float = 0.0) -> tuple[str | None, dict | None]:
    """Prefer 1m momentum scalp for movers — movement only, no SMC."""
    try:
        candles_1m = futures_client.get_futures_candles(symbol, "1m", 30)
    except Exception:
        candles_1m = []

    if len(candles_1m) >= 8:
        df_1m = futures_client.candles_to_df(candles_1m)
        result = momentum_scalp(df_1m, change_24h)
        if result.fired and result.stop_loss:
            decision = evaluate_trade_decision("momentum_scalp", result, regime, category)
            if decision["can_take"]:
                return "momentum_scalp", {
                    "setup": "momentum_scalp",
                    "confidence": decision["take_confidence"],
                    "direction": "LONG" if result.direction == "bullish" else "SHORT",
                    "proposed_stop": float(result.stop_loss),
                    "reason": result.reason,
                    "sl_basis": result.sl_basis,
                    "priority": 0,
                    "scalp_tight": True,
                }

    from app.signals.setups import SETUP_FUNCTIONS

    best_name: str | None = None
    best: dict | None = None
    for name, fn in SETUP_FUNCTIONS.items():
        try:
            result = fn(df)
        except Exception:
            continue
        if not result.fired or not result.stop_loss:
            continue
        decision = evaluate_trade_decision(name, result, regime, category)
        if not decision["can_take"]:
            continue
        conf = decision["take_confidence"]
        if best is None or conf > best["confidence"]:
            best_name = name
            best = {
                "setup": name,
                "confidence": conf,
                "direction": "LONG" if result.direction == "bullish" else "SHORT",
                "proposed_stop": float(result.stop_loss),
                "reason": result.reason,
                "sl_basis": result.sl_basis,
                "priority": SETUP_PRIORITY.get(name, 9),
            }
    return best_name, best


def analyze_mover_symbol(sym: WatchlistSymbol, force: bool = False) -> dict:
    """Fresh Entry / SL / TP1 for a top mover — valid for ~12 minutes."""
    symbol = sym.symbol.upper()
    if _cache_valid(symbol, force):
        return dict(_cache[symbol]["data"])

    settings = get_settings()
    now = datetime.now(timezone.utc)
    ttl = _ttl_minutes()
    valid_until = now + timedelta(minutes=ttl)
    category = sym.category if sym.category in ("meme", "mover", "major", "alt") else "mover"

    live_list = [
        s for s in crypto_scanner.get_active_signals()
        if (s.get("symbol") or "").upper() == symbol
    ]
    live = live_list[0] if live_list else None

    try:
        candles = futures_client.get_futures_candles(symbol, "5m", 120)
    except Exception:
        candles = []

    if len(candles) < 30:
        return _fallback(sym, now, valid_until, ttl, "loading candles")

    df = futures_client.candles_to_df(candles)
    bar = df.iloc[-1]
    price = float(bar["close"])
    regime = detect_regime(df)
    swing_high, swing_low = swing_high_low(df)
    atr_p = atr_pct(df)
    atr_val = price * atr_p / 100.0 if atr_p > 0 else price * 0.008
    mid = (swing_high + swing_low) / 2

    setup_name, setup = _best_setup(symbol, df, regime, category, sym.change_pct_24h)

    if live:
        direction = (live.get("direction") or "LONG").upper()
        entry = float(live.get("entry_price") or price)
        sl = float(live.get("stop_loss_price") or swing_low)
        t1 = float(live.get("target_1_price") or entry)
        confidence = int(live.get("confidence") or 70)
        setup_name = live.get("setup") or setup_name
        entry_time_raw = live.get("timestamp") or now.isoformat()
        try:
            entry_dt = datetime.fromisoformat(str(entry_time_raw).replace("Z", "+00:00"))
            if entry_dt.tzinfo is None:
                entry_dt = entry_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            entry_dt = now
        source = "live_signal"
    elif setup:
        direction = setup["direction"]
        entry = price
        sl = normalize_stop_loss(
            entry=entry,
            direction="bullish" if direction == "LONG" else "bearish",
            proposed_stop=setup["proposed_stop"],
            bar_low=float(bar["low"]),
            bar_high=float(bar["high"]),
            swing_low=swing_low,
            swing_high=swing_high,
            atr=atr_val,
            tier=sym.tier,
            scalp_tight=bool(setup.get("scalp_tight")),
        )
        risk = abs(entry - sl)
        if risk <= 0:
            return _fallback(sym, now, valid_until, ttl, "invalid risk")
        sign = 1 if direction == "LONG" else -1
        t1 = entry + sign * risk * T1_R
        confidence = setup["confidence"]
        entry_dt = now
        source = "structure_scan"
    else:
        mom = (float(df["close"].iloc[-1]) - float(df["close"].iloc[-12])) / float(df["close"].iloc[-12]) * 100
        if sym.change_pct_24h >= 3 or mom > 0.2:
            direction = "LONG"
            prediction = "bullish"
        elif sym.change_pct_24h <= -3 or mom < -0.2:
            direction = "SHORT"
            prediction = "bearish"
        else:
            direction = "LONG" if price >= mid else "SHORT"
            prediction = "bullish" if direction == "LONG" else "bearish"
        entry = price
        sl = swing_low if direction == "LONG" else swing_high
        sl = normalize_stop_loss(
            entry=entry,
            direction="bullish" if direction == "LONG" else "bearish",
            proposed_stop=sl,
            bar_low=float(bar["low"]),
            bar_high=float(bar["high"]),
            swing_low=swing_low,
            swing_high=swing_high,
            atr=atr_val,
            tier=sym.tier,
            scalp_tight=True,
        )
        risk = abs(entry - sl)
        if risk <= 0:
            return _fallback(sym, now, valid_until, ttl, "invalid risk")
        sign = 1 if direction == "LONG" else -1
        t1 = entry + sign * risk * T1_R
        confidence = max(51, min(78, 55 + int(abs(sym.change_pct_24h))))
        entry_dt = now
        source = "momentum"
        setup_name = setup_name or "market_structure"

    prediction = "bullish" if direction == "LONG" else "bearish"
    risk = abs(entry - sl)
    expected_move_pct = round(abs(t1 - entry) / entry * 100, 2) if entry > 0 else 0.0
    bullish_pct = confidence if prediction == "bullish" else max(51, 100 - confidence)

    if prediction == "bullish":
        exp_low, exp_high = min(entry, price), max(t1, swing_high)
    else:
        exp_high, exp_low = max(entry, price), min(t1, swing_low)

    label = _SETUP_LABELS.get(setup_name or "", "Market Structure")
    chart_note = (
        f"{label} · {'↑' if prediction == 'bullish' else '↓'} "
        f"expected {expected_move_pct:.1f}% to TP1 · refresh every {ttl}m"
    )

    data = {
        "entry_price": round(entry, 8),
        "stop_loss_price": round(sl, 8),
        "target_1_price": round(t1, 8),
        "direction": direction,
        "prediction": prediction,
        "confidence": confidence,
        "bullish_pct": bullish_pct,
        "expected_move_pct": expected_move_pct,
        "entry_time": entry_dt.isoformat(),
        "valid_until": valid_until.isoformat(),
        "levels_ttl_minutes": ttl,
        "levels_source": source,
        "strategy": setup_name,
        "strategy_label": label,
        "suggestion": (
            f"{'LONG' if direction == 'LONG' else 'SHORT'} — enter before {valid_until.strftime('%H:%M')} UTC "
            f"or wait for next refresh"
        ),
        "chart": {
            "support": round(swing_low, 8),
            "resistance": round(swing_high, 8),
            "strategy_line": round(entry, 8),
            "stop_loss": round(sl, 8),
            "target": round(t1, 8),
            "expected_move_low": round(exp_low, 8),
            "expected_move_high": round(exp_high, 8),
            "prediction": prediction,
            "note": chart_note,
        },
        "tracker": {
            "symbol": symbol,
            "base": sym.base,
            "action": "BUY" if direction == "LONG" else "SELL",
            "prediction": prediction,
            "confidence": confidence,
            "bullish_pct": bullish_pct,
            "expected_move_pct": expected_move_pct,
            "strategy_label": label,
            "suggestion": chart_note,
            "entry_time": entry_dt.isoformat(),
            "valid_until": valid_until.isoformat(),
            "levels_ttl_minutes": ttl,
            "chart": {
                "support": round(swing_low, 8),
                "resistance": round(swing_high, 8),
                "strategy_line": round(entry, 8),
                "stop_loss": round(sl, 8),
                "target": round(t1, 8),
                "expected_move_low": round(exp_low, 8),
                "expected_move_high": round(exp_high, 8),
                "prediction": prediction,
                "note": chart_note,
            },
        },
        "has_live_signal": live is not None,
    }

    _cache[symbol] = {"cached_at": now, "data": data}
    return dict(data)


def _fallback(sym: WatchlistSymbol, now: datetime, valid_until: datetime, ttl: int, reason: str) -> dict:
    data = {
        "entry_price": sym.last_price,
        "stop_loss_price": 0.0,
        "target_1_price": 0.0,
        "direction": "LONG" if sym.change_pct_24h >= 0 else "SHORT",
        "prediction": "bullish" if sym.change_pct_24h >= 0 else "bearish",
        "confidence": 51,
        "bullish_pct": 55 if sym.change_pct_24h >= 0 else 45,
        "expected_move_pct": 0.0,
        "entry_time": now.isoformat(),
        "valid_until": valid_until.isoformat(),
        "levels_ttl_minutes": ttl,
        "levels_source": "fallback",
        "strategy": None,
        "strategy_label": "Loading",
        "suggestion": f"WAIT — {reason}",
        "chart": {"prediction": "neutral", "note": reason},
        "tracker": None,
        "has_live_signal": False,
    }
    _cache[sym.symbol.upper()] = {"cached_at": now, "data": data}
    return dict(data)


def refresh_mover_trackers(symbols: list[WatchlistSymbol] | None = None, force: bool = True) -> int:
    from app.services.crypto_watchlist import get_top_24h_movers

    items = symbols or get_top_24h_movers()
    n = 0
    for sym in items:
        try:
            analyze_mover_symbol(sym, force=force)
            n += 1
        except Exception:
            logger.exception("Mover tracker failed for %s", sym.symbol)
    logger.info("Mover levels refreshed for %d coins (%dm TTL)", n, _ttl_minutes())
    return n


def attach_mover_tracker(coin_dict: dict, sym: WatchlistSymbol, force: bool = False) -> dict:
    """Merge tracker levels into markets coin row."""
    levels = analyze_mover_symbol(sym, force=force)
    out = dict(coin_dict)
    out.update(levels)
    return out
