"""BTC & Gold focus tracker — structure bias, strategy line, buy/sell suggestion."""

from __future__ import annotations

import logging

from app.services.crypto_futures_client import futures_client
from app.signals.crypto_scanner import crypto_scanner
from app.signals.market_structure import swing_high_low
from app.signals.regime import detect_regime
from app.signals.setups import SETUP_FUNCTIONS
from app.signals.trade_decision import SETUP_PRIORITY, evaluate_trade_decision

logger = logging.getLogger(__name__)

_news_cache: dict = {"at": None, "items": []}

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
    "fvg_retest": "FVG Retest",
    "fibonacci_retrace": "Fibonacci",
    "structure_reversal": "Structure Reversal",
    "orb_breakout": "ORB Breakout",
}


def _structure_note(regime, swing_high: float, swing_low: float, price: float) -> str:
    mid = (swing_high + swing_low) / 2
    if regime.trend_direction == "bullish":
        return f"Bullish structure — {regime.summary}, holding above mid"
    if regime.trend_direction == "bearish":
        return f"Bearish structure — {regime.summary}, below mid"
    if price >= mid:
        return f"Neutral-bullish — price above range mid ({regime.summary})"
    return f"Neutral-bearish — price below range mid ({regime.summary})"


def _suggestion(action: str, prediction: str, setup_name: str | None, has_signal: bool) -> str:
    label = _SETUP_LABELS.get(setup_name or "", setup_name or "structure")
    if has_signal and action == "BUY":
        return f"BUY bias — {label} active · enter on 1m confirm"
    if has_signal and action == "SELL":
        return f"SELL bias — {label} active · short on 1m confirm"
    if action == "BUY":
        return f"Bullish prediction — watch {label} retest or sweep of lows"
    if action == "SELL":
        return f"Bearish prediction — watch {label} rejection or sweep of highs"
    return "WAIT — no clear edge; let structure form"


def _best_setup(df, regime) -> tuple[str | None, dict | None]:
    best_name: str | None = None
    best: dict | None = None
    for name, fn in SETUP_FUNCTIONS.items():
        try:
            result = fn(df)
        except Exception:
            continue
        if not result.fired:
            continue
        decision = evaluate_trade_decision(name, result, regime, "major")
        if not decision["can_take"]:
            continue
        conf = decision["take_confidence"]
        if best is None or conf > best["confidence"]:
            pri = SETUP_PRIORITY.get(name, 9)
            best_name = name
            best = {
                "setup": name,
                "confidence": conf,
                "direction": "LONG" if result.direction == "bullish" else "SHORT",
                "entry": result.entry,
                "stop_loss": result.stop_loss,
                "target": result.targets[0] if result.targets else None,
                "reason": result.reason,
                "priority": pri,
            }
    return best_name, best


def _news_context(base: str) -> dict:
    """Light news bias for BTC / GOLD (cached 2 min)."""
    from datetime import datetime, timedelta, timezone

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


def analyze_focus_pair(symbol: str, base: str, icon: str) -> dict:
    candles = futures_client.get_futures_candles(symbol, "5m", 120)
    if len(candles) < 30:
        return _fallback(symbol, base, icon, "insufficient data")

    df = futures_client.candles_to_df(candles)
    bar = df.iloc[-1]
    price = float(bar["close"])
    regime = detect_regime(df)
    swing_high, swing_low = swing_high_low(df)
    mid = (swing_high + swing_low) / 2

    setup_name, setup = _best_setup(df, regime)
    live_signals = [
        s for s in crypto_scanner.get_active_signals()
        if (s.get("symbol") or "").upper() == symbol.upper()
    ]
    live = live_signals[0] if live_signals else None

    # Prediction from structure + momentum + setup direction
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
        if setup["direction"] == "LONG":
            score += 2
        else:
            score -= 2

    if score >= 2:
        prediction = "bullish"
        action = "BUY"
    elif score <= -2:
        prediction = "bearish"
        action = "SELL"
    else:
        prediction = "neutral"
        action = "WAIT"

    if live:
        action = "BUY" if (live.get("direction") or "").upper() == "LONG" else "SELL"
        prediction = "bullish" if action == "BUY" else "bearish"
        setup_name = live.get("setup") or setup_name
        entry = float(live.get("entry_price") or price)
        sl = float(live.get("stop_loss_price") or swing_low)
        target = float(live.get("target_1_price") or swing_high)
        confidence = int(live.get("confidence") or 80)
    elif setup:
        entry = float(setup["entry"] or price)
        sl = float(setup["stop_loss"] or swing_low)
        target = float(setup["target"] or swing_high)
        confidence = setup["confidence"]
        action = "BUY" if setup["direction"] == "LONG" else "SELL"
        prediction = "bullish" if action == "BUY" else "bearish"
    else:
        entry = mid
        sl = swing_low if prediction != "bearish" else swing_high
        target = swing_high if prediction != "bearish" else swing_low
        confidence = max(55, min(72, 60 + abs(score) * 5))

    news = _news_context(base)
    if prediction == "bullish" and news["bias"] == "bearish":
        confidence = max(50, confidence - 5)
    elif prediction == "bearish" and news["bias"] == "bullish":
        confidence = max(50, confidence - 5)
    elif prediction == news["bias"] and prediction != "neutral":
        confidence = min(95, confidence + 4)

    if prediction == "bullish":
        exp_low, exp_high = min(entry, price), max(target, swing_high)
    elif prediction == "bearish":
        exp_high, exp_low = max(entry, price), min(target, swing_low)
    else:
        exp_low, exp_high = swing_low, swing_high

    chart_note = (
        f"{_SETUP_LABELS.get(setup_name or '', 'Structure')} · "
        f"{'↑' if prediction == 'bullish' else '↓' if prediction == 'bearish' else '↔'} "
        f"expected move to {round(exp_high if prediction != 'bearish' else exp_low, 2)}"
    )

    return {
        "symbol": symbol,
        "base": base,
        "icon": icon,
        "last_price": round(price, 8),
        "prediction": prediction,
        "action": action,
        "confidence": confidence,
        "strategy": setup_name,
        "strategy_label": _SETUP_LABELS.get(setup_name or "", "Market Structure"),
        "suggestion": _suggestion(action, prediction, setup_name, live is not None),
        "market_structure": _structure_note(regime, swing_high, swing_low, price),
        "momentum_pct": round(mom, 3),
        "regime": regime.regime.value,
        "trend_direction": regime.trend_direction,
        "levels": {
            "support": round(swing_low, 8),
            "resistance": round(swing_high, 8),
            "strategy_line": round(entry, 8),
            "stop_loss": round(sl, 8),
            "target": round(target, 8),
            "expected_move_low": round(exp_low, 8),
            "expected_move_high": round(exp_high, 8),
        },
        "chart": {
            "support": round(swing_low, 8),
            "resistance": round(swing_high, 8),
            "strategy_line": round(entry, 8),
            "stop_loss": round(sl, 8),
            "target": round(target, 8),
            "expected_move_low": round(exp_low, 8),
            "expected_move_high": round(exp_high, 8),
            "prediction": prediction,
            "note": chart_note,
        },
        "news_context": news,
        "has_live_signal": live is not None,
        "live_signal": {
            "direction": live.get("direction"),
            "setup": live.get("setup"),
            "confidence": live.get("confidence"),
        } if live else None,
    }


def _fallback(symbol: str, base: str, icon: str, reason: str) -> dict:
    return {
        "symbol": symbol,
        "base": base,
        "icon": icon,
        "last_price": 0,
        "prediction": "neutral",
        "action": "WAIT",
        "confidence": 0,
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


def get_btc_gold_tracker() -> list[dict]:
    out: list[dict] = []
    for sym, base, icon in FOCUS_PAIRS:
        try:
            out.append(analyze_focus_pair(sym, base, icon))
        except Exception:
            logger.exception("Focus tracker failed for %s", sym)
            out.append(_fallback(sym, base, icon, "analysis unavailable"))
    return out
