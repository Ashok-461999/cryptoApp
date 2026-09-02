"""BTC & Gold focus tracker — fresh Entry / SL / TP1 every 10–15 min from live prediction."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services.crypto_futures_client import futures_client
from app.signals.crypto_scanner import crypto_scanner
from app.signals.indicators import atr_pct
from app.signals.market_structure import swing_high_low
from app.signals.regime import detect_regime
from app.signals.schemas import T1_R
from app.signals.setups import SETUP_FUNCTIONS
from app.signals.sl_levels import normalize_stop_loss
from app.signals.trade_decision import SETUP_PRIORITY, evaluate_trade_decision

logger = logging.getLogger(__name__)

_news_cache: dict = {"at": None, "items": []}
_focus_cache: dict[str, dict] = {}

FOCUS_PAIRS = (
    ("BTCUSDT", "BTC", "🟡"),
    ("PAXGUSDT", "GOLD", "🥇"),
)

_SETUP_LABELS = {
    "structure_fib_sweep": "Structure+Fib+Sweep",
    "liquidity_sweep": "Liquidity Sweep",
    "amd_model": "AMD Model",
    "ifvg_reversal": "IFVG",
    "order_flow": "Order Flow",
    "anchored_vwap": "Anchored VWAP",
    "volume_profile": "Volume Profile",
    "supply_demand": "Supply & Demand",
    "fibonacci_retrace": "Fibonacci",
    "structure_reversal": "Structure Reversal",
}


def _ttl_minutes() -> int:
    return max(10, min(15, get_settings().mover_levels_refresh_minutes))


def _cache_valid(symbol: str, force: bool) -> bool:
    if force:
        return False
    row = _focus_cache.get(symbol.upper())
    if not row:
        return False
    at = row.get("cached_at")
    if not isinstance(at, datetime):
        return False
    return datetime.now(timezone.utc) - at < timedelta(minutes=_ttl_minutes())


def _structure_note(regime, swing_high: float, swing_low: float, price: float) -> str:
    mid = (swing_high + swing_low) / 2
    if regime.trend_direction == "bullish":
        return f"Bullish structure — {regime.summary}, holding above mid"
    if regime.trend_direction == "bearish":
        return f"Bearish structure — {regime.summary}, below mid"
    if price >= mid:
        return f"Neutral-bullish — price above range mid ({regime.summary})"
    return f"Neutral-bearish — price below range mid ({regime.summary})"


def _suggestion(action: str, prediction: str, setup_name: str | None, has_signal: bool, valid_until: datetime) -> str:
    label = _SETUP_LABELS.get(setup_name or "", setup_name or "structure")
    until = valid_until.strftime("%H:%M UTC")
    if action == "WAIT":
        return f"WAIT — no clear edge; fresh levels at {until}"
    if has_signal and action == "BUY":
        return f"BUY — {label} · enter before {until} or wait for refresh"
    if has_signal and action == "SELL":
        return f"SELL — {label} · short before {until} or wait for refresh"
    if action == "BUY":
        return f"Bullish prediction — {label} · entry valid until {until}"
    return f"Bearish prediction — {label} · entry valid until {until}"


def _best_setup(df, regime) -> tuple[str | None, dict | None]:
    best_name: str | None = None
    best: dict | None = None
    for name, fn in SETUP_FUNCTIONS.items():
        try:
            result = fn(df)
        except Exception:
            continue
        if not result.fired or not result.stop_loss:
            continue
        decision = evaluate_trade_decision(name, result, regime, "major")
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


def _parse_ts(raw: str | None, fallback: datetime) -> datetime:
    if not raw:
        return fallback
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return fallback


def _live_is_fresh(live: dict, now: datetime, ttl: int) -> bool:
    ts = _parse_ts(live.get("timestamp"), now)
    return (now - ts) < timedelta(minutes=ttl)


def _news_context(base: str) -> dict:
    global _news_cache
    now = datetime.now(timezone.utc)
    cached_at = _news_cache.get("at")
    if cached_at and (now - cached_at) < timedelta(minutes=2):
        items = _news_cache.get("items") or []
    else:
        try:
            from app.services.market_news import fetch_market_news
            items = fetch_market_news(25).get("items") or []
            _news_cache = {"at": now, "items": items}
        except Exception:
            items = _news_cache.get("items") or []

    tag = "BTC" if base == "BTC" else "GOLD"
    related = [i for i in items if tag in (i.get("affected_markets") or [])]
    if not related and base == "BTC":
        related = [i for i in items if "BTC" in (i.get("affected_markets") or [])]
    if not related:
        related = items[:3]

    bull = sum(1 for i in related if i.get("sentiment") == "bullish")
    bear = sum(1 for i in related if i.get("sentiment") == "bearish")
    if bull > bear:
        bias = "bullish"
    elif bear > bull:
        bias = "bearish"
    else:
        bias = "neutral"

    top = related[0] if related else {}
    title = (top.get("title") or "No major headline")[:120]
    return {
        "bias": bias,
        "headline": title,
        "bullish_count": bull,
        "bearish_count": bear,
        "note": f"News flow {bias.upper()} for {base} — {bull} bull / {bear} bear headlines",
    }


def _compute_levels(
    *,
    price: float,
    direction: str,
    proposed_sl: float,
    bar_low: float,
    bar_high: float,
    swing_low: float,
    swing_high: float,
    atr_val: float,
    tier: str,
    rr: float = 2.0,
) -> tuple[float, float, float]:
    """Entry at current price, normalized SL, TP1 at 1:2 R:R."""
    entry = price
    sl = normalize_stop_loss(
        entry=entry,
        direction="bullish" if direction == "LONG" else "bearish",
        proposed_stop=proposed_sl,
        bar_low=bar_low,
        bar_high=bar_high,
        swing_low=swing_low,
        swing_high=swing_high,
        atr=atr_val,
        tier=tier,
    )
    risk = abs(entry - sl)
    if risk <= 0:
        risk = entry * 0.005
        sl = entry - risk if direction == "LONG" else entry + risk
    sign = 1 if direction == "LONG" else -1
    t1 = entry + sign * risk * rr
    return entry, sl, t1


def analyze_focus_pair(symbol: str, base: str, icon: str, force: bool = False) -> dict:
    sym = symbol.upper()
    if _cache_valid(sym, force):
        return dict(_focus_cache[sym]["data"])

    now = datetime.now(timezone.utc)
    ttl = _ttl_minutes()
    valid_until = now + timedelta(minutes=ttl)

    candles = futures_client.get_futures_candles(symbol, "5m", 120)
    htf_candles = futures_client.get_futures_candles(symbol, "1h", 48)
    if len(candles) < 30:
        return _fallback(symbol, base, icon, "insufficient data", now, valid_until, ttl)

    df = futures_client.candles_to_df(candles)
    htf_df = futures_client.candles_to_df(htf_candles)
    bar = df.iloc[-1]
    price = float(bar["close"])
    regime = detect_regime(df)
    if len(htf_df) >= 20:
        swing_high, swing_low = swing_high_low(htf_df, lookback=20)
    else:
        swing_high, swing_low = swing_high_low(df)
    atr_p = atr_pct(df)
    atr_val = price * atr_p / 100.0 if atr_p > 0 else price * 0.008
    mid = (swing_high + swing_low) / 2
    tier = "A" if base == "BTC" else "B"

    setup_name, setup = _best_setup(df, regime)
    live_list = [s for s in crypto_scanner.get_active_signals() if (s.get("symbol") or "").upper() == sym]
    live = live_list[0] if live_list else None
    live_fresh = live is not None and _live_is_fresh(live, now, ttl)

    recent = df.tail(12)
    mom = (float(recent["close"].iloc[-1]) - float(recent["close"].iloc[0])) / float(recent["close"].iloc[0]) * 100
    score = 0
    if regime.trend_direction == "bullish":
        score += 2
    elif regime.trend_direction == "bearish":
        score -= 2
    if price > mid:
        score += 1
    else:
        score -= 1
    if mom > 0.15:
        score += 1
    elif mom < -0.15:
        score -= 1
    if setup:
        score += 2 if setup["direction"] == "LONG" else -2

    if score >= 2:
        prediction = "bullish"
        action = "BUY"
        direction = "LONG"
    elif score <= -2:
        prediction = "bearish"
        action = "SELL"
        direction = "SHORT"
    else:
        prediction = "neutral"
        action = "WAIT"
        direction = "LONG" if price >= mid else "SHORT"

    entry_dt = now
    levels_source = "structure"
    target_2 = 0.0
    move_usdt = 0.0

    if live_fresh:
        direction = (live.get("direction") or "LONG").upper()
        if direction == "STRADDLE":
            direction = "LONG" if price >= mid else "SHORT"
        action = "BUY" if direction == "LONG" else "SELL"
        prediction = "bullish" if direction == "LONG" else "bearish"
        entry = price
        entry, sl, target = _compute_levels(
            price=price,
            direction=direction,
            proposed_sl=float(live.get("stop_loss_price") or swing_low),
            bar_low=float(bar["low"]),
            bar_high=float(bar["high"]),
            swing_low=swing_low,
            swing_high=swing_high,
            atr_val=atr_val,
            tier=tier,
        )
        setup_name = live.get("setup") or setup_name
        confidence = int(live.get("confidence") or 80)
        entry_dt = _parse_ts(live.get("timestamp"), now)
        levels_source = "live_signal"
    elif setup and action != "WAIT":
        direction = setup["direction"]
        action = "BUY" if direction == "LONG" else "SELL"
        prediction = "bullish" if direction == "LONG" else "bearish"
        setup_name = setup["setup"]
        entry, sl, target = _compute_levels(
            price=price,
            direction=direction,
            proposed_sl=setup["proposed_stop"],
            bar_low=float(bar["low"]),
            bar_high=float(bar["high"]),
            swing_low=swing_low,
            swing_high=swing_high,
            atr_val=atr_val,
            tier=tier,
        )
        confidence = setup["confidence"]
        levels_source = "setup_scan"
    elif action != "WAIT":
        entry, sl, target = _compute_levels(
            price=price,
            direction=direction,
            proposed_sl=swing_low if direction == "LONG" else swing_high,
            bar_low=float(bar["low"]),
            bar_high=float(bar["high"]),
            swing_low=swing_low,
            swing_high=swing_high,
            atr_val=atr_val,
            tier=tier,
        )
        confidence = max(55, min(78, 60 + abs(score) * 5))
        levels_source = "momentum"
    else:
        entry = price
        sl = 0.0
        target = 0.0
        confidence = max(50, min(65, 55 + abs(int(score))))

    from app.services.binance_derivatives import get_derivatives_snapshot

    news = _news_context(base)
    deriv = get_derivatives_snapshot(sym, swing_high=swing_high, swing_low=swing_low, price=price)
    if action != "WAIT":
        if prediction == "bullish" and news["bias"] == "bearish":
            confidence = max(50, confidence - 5)
        elif prediction == "bearish" and news["bias"] == "bullish":
            confidence = max(50, confidence - 5)
        elif prediction == news["bias"]:
            confidence = min(95, confidence + 4)

    expected_move_pct = round(abs(target - entry) / entry * 100, 2) if entry > 0 and target > 0 else 0.0
    bullish_pct = confidence if prediction == "bullish" else (100 - confidence if prediction == "bearish" else 50)

    if prediction == "bullish" and target > 0:
        exp_low, exp_high = min(entry, price), max(target, swing_high)
    elif prediction == "bearish" and target > 0:
        exp_high, exp_low = max(entry, price), min(target, swing_low)
    else:
        exp_low, exp_high = swing_low, swing_high

    label = _SETUP_LABELS.get(setup_name or "", "Market Structure")
    chart_note = (
        f"{label} · {'↑' if prediction == 'bullish' else '↓' if prediction == 'bearish' else '↔'} "
        f"{'expected ' + str(expected_move_pct) + '% to TP1' if action != 'WAIT' else 'no trade yet'}"
    )

    data = {
        "symbol": symbol,
        "base": base,
        "icon": icon,
        "last_price": round(price, 8),
        "prediction": prediction,
        "action": action,
        "direction": direction if action != "WAIT" else None,
        "confidence": confidence,
        "bullish_pct": bullish_pct,
        "expected_move_pct": expected_move_pct,
        "entry_price": round(entry, 8) if action != "WAIT" else None,
        "stop_loss_price": round(sl, 8) if action != "WAIT" else None,
        "target_1_price": round(target, 8) if action != "WAIT" else None,
        "target_2_price": None,
        "target_move_usdt": round(move_usdt, 1) if move_usdt else None,
        "entry_time": entry_dt.isoformat(),
        "valid_until": valid_until.isoformat(),
        "levels_ttl_minutes": ttl,
        "levels_source": levels_source,
        "strategy": setup_name,
        "strategy_label": label,
        "suggestion": _suggestion(action, prediction, setup_name, live_fresh, valid_until),
        "market_structure": _structure_note(regime, swing_high, swing_low, price),
        "momentum_pct": round(mom, 3),
        "regime": regime.regime.value,
        "trend_direction": regime.trend_direction,
        "levels": {
            "support": round(swing_low, 8),
            "resistance": round(swing_high, 8),
            "strategy_line": round(entry, 8) if action != "WAIT" else round(mid, 8),
            "entry": round(entry, 8) if action != "WAIT" else None,
            "stop_loss": round(sl, 8) if action != "WAIT" else None,
            "target": round(target, 8) if action != "WAIT" else None,
            "target_2": None,
            "target_move_usdt": round(move_usdt, 1) if move_usdt else None,
            "expected_move_low": round(exp_low, 8),
            "expected_move_high": round(exp_high, 8),
        },
        "chart": {
            "support": round(swing_low, 8),
            "resistance": round(swing_high, 8),
            "strategy_line": round(entry, 8) if action != "WAIT" else round(mid, 8),
            "stop_loss": round(sl, 8) if action != "WAIT" else None,
            "target": round(target, 8) if action != "WAIT" else None,
            "target_2": None,
            "target_move_usdt": round(move_usdt, 1) if move_usdt else None,
            "expected_move_low": round(exp_low, 8),
            "expected_move_high": round(exp_high, 8),
            "prediction": prediction,
            "note": chart_note,
        },
        "news_context": news,
        "has_live_signal": live_fresh,
        "live_signal": {
            "direction": live.get("direction"),
            "setup": live.get("setup"),
            "confidence": live.get("confidence"),
        } if live_fresh else None,
        "derivatives": {
            "open_interest_usdt": deriv.get("open_interest_usdt", 0),
            "funding_pct_8h": deriv.get("funding_pct_8h", 0),
            "long_short_ratio": deriv.get("long_short_ratio", 1),
            "taker_buy_sell_ratio": deriv.get("taker_buy_sell_ratio", 1),
            "funding_regime": deriv.get("funding_regime", "neutral"),
        },
    }

    _focus_cache[sym] = {"cached_at": now, "data": data}
    return dict(data)


def _fallback(symbol: str, base: str, icon: str, reason: str, now: datetime, valid_until: datetime, ttl: int) -> dict:
    data = {
        "symbol": symbol,
        "base": base,
        "icon": icon,
        "last_price": 0,
        "prediction": "neutral",
        "action": "WAIT",
        "direction": None,
        "confidence": 0,
        "bullish_pct": 50,
        "expected_move_pct": 0.0,
        "entry_price": None,
        "stop_loss_price": None,
        "target_1_price": None,
        "entry_time": now.isoformat(),
        "valid_until": valid_until.isoformat(),
        "levels_ttl_minutes": ttl,
        "levels_source": "fallback",
        "strategy": None,
        "strategy_label": "Loading",
        "suggestion": f"WAIT — {reason}",
        "market_structure": reason,
        "momentum_pct": 0,
        "regime": "unknown",
        "trend_direction": "neutral",
        "levels": {"support": 0, "resistance": 0, "strategy_line": 0, "stop_loss": 0, "target": 0,
                   "expected_move_low": 0, "expected_move_high": 0},
        "chart": {"support": 0, "resistance": 0, "strategy_line": 0, "prediction": "neutral", "note": reason},
        "news_context": {"bias": "neutral", "headline": "", "note": reason, "bullish_count": 0, "bearish_count": 0},
        "has_live_signal": False,
        "live_signal": None,
    }
    _focus_cache[symbol.upper()] = {"cached_at": now, "data": data}
    return dict(data)


def refresh_focus_trackers(force: bool = True) -> int:
    n = 0
    for sym, base, icon in FOCUS_PAIRS:
        try:
            analyze_focus_pair(sym, base, icon, force=force)
            n += 1
        except Exception:
            logger.exception("Focus tracker refresh failed for %s", sym)
    logger.info("BTC/Gold levels refreshed (%dm TTL)", _ttl_minutes())
    return n


def get_btc_gold_tracker(force: bool = False) -> list[dict]:
    out: list[dict] = []
    for sym, base, icon in FOCUS_PAIRS:
        try:
            out.append(analyze_focus_pair(sym, base, icon, force=force))
        except Exception:
            logger.exception("Focus tracker failed for %s", sym)
            now = datetime.now(timezone.utc)
            out.append(_fallback(sym, base, icon, "analysis unavailable", now, now + timedelta(minutes=_ttl_minutes()), _ttl_minutes()))
    return out
