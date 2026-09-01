"""Delta × Binance Alpha Engine — 0-100 confluence, predictions, derivatives, news."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from datetime import datetime, timezone

import pandas as pd

from app.config import Settings, get_settings
from app.services.binance_derivatives import get_derivatives_snapshot
from app.services.delta_client import delta_client
from app.services.market_news import detect_market_impact, fetch_market_news, score_sentiment
from app.signals.market_structure import swing_high_low
from app.signals.regime import Regime, RegimeSnapshot
from app.signals.schemas import SetupResult
from app.signals.volume_profile import profile_levels

logger = logging.getLogger(__name__)

CORE_PAIRS = frozenset({"BTCUSDT", "PAXGUSDT", "ETHUSDT"})
LIQUIDITY_SETUPS = frozenset({
    "amd_model", "structure_fib_sweep", "ifvg_reversal", "order_flow", "structure_reversal",
})
STRUCTURE_SETUPS = frozenset({
    "structure_fib_sweep", "amd_model", "structure_reversal", "fibonacci_retrace", "ifvg_reversal",
})


@dataclass
class HtfBias:
    bias: str
    summary: str
    in_range_mid: bool = False
    premium_zone: bool = False
    discount_zone: bool = False
    inside_value_area: bool = False


@dataclass
class Confluence100:
    score: int
    breakdown: dict[str, int] = field(default_factory=dict)
    factors: list[str] = field(default_factory=list)
    grade: str = "B"
    tier_label: str = "B"

    @property
    def label(self) -> str:
        return f"{self.score}/100"


def htf_bias_smc(df: pd.DataFrame, mp: tuple[float, float, float] | None = None) -> HtfBias:
    """HTF bias from SMC structure only — no lagging indicators."""
    if df is None or len(df) < 20:
        return HtfBias("neutral", "Insufficient HTF data")
    sh, sl = swing_high_low(df, lookback=12)
    price = float(df.iloc[-1]["close"])
    rng = sh - sl
    if rng <= 0:
        return HtfBias("neutral", "Flat HTF range")
    pos = (price - sl) / rng
    in_mid = 0.40 <= pos <= 0.60
    premium = pos >= 0.62
    discount = pos <= 0.38
    recent = df.tail(10)
    hh = float(recent["high"].iloc[-1]) > float(recent["high"].iloc[-5])
    hl = float(recent["low"].iloc[-1]) > float(recent["low"].iloc[-5])
    lh = float(recent["high"].iloc[-1]) < float(recent["high"].iloc[-5])
    ll = float(recent["low"].iloc[-1]) < float(recent["low"].iloc[-5])
    if hh and hl:
        bias, tag = "bullish", "HH/HL structure"
    elif lh and ll:
        bias, tag = "bearish", "LH/LL structure"
    else:
        bias, tag = "neutral", "Mixed structure"
    inside_va = False
    if mp:
        poc, val, vah = mp
        inside_va = val <= price <= vah
    summary = f"HTF {bias} — {tag} ({pos * 100:.0f}% of range)"
    if inside_va:
        summary += " · inside value area (chop risk)"
    elif premium:
        summary += " · premium zone"
    elif discount:
        summary += " · discount zone"
    return HtfBias(bias, summary, in_range_mid=in_mid, premium_zone=premium, discount_zone=discount, inside_value_area=inside_va)


def _dir_ok(direction: str, bias: str) -> bool:
    d = direction.upper()
    if bias == "neutral":
        return True
    return (d == "LONG" and bias == "bullish") or (d == "SHORT" and bias == "bearish")


def news_sentiment_for_symbol(symbol: str) -> dict:
    base = symbol.replace("USDT", "")
    tag = "BTC" if base == "BTC" else ("GOLD" if base == "PAXG" else ("ETH" if base == "ETH" else base))
    news = fetch_market_news(20)
    items = news.get("items") or []
    related = [i for i in items if tag in (i.get("affected_markets") or [])]
    if not related and base == "BTC":
        related = [i for i in items if "BTC" in (i.get("affected_markets") or [])]
    if not related:
        related = items[:2]
    top = related[0] if related else {}
    title = (top.get("title") or "No major headline")[:120]
    sent_score = int(top.get("sentiment_score") or 0)
    sent_label = top.get("sentiment") or "neutral"
    impact = top.get("impact_level") or "low"
    return {
        "headline": title,
        "source": top.get("source") or "",
        "impact": impact,
        "sentiment_score": sent_score,
        "sentiment": sent_label,
        "news_points": _news_points(sent_score, sent_label),
    }


def _news_points(score: int, label: str) -> int:
    if label == "bullish":
        return min(10, max(0, 5 + score // 25))
    if label == "bearish":
        return max(0, 5 + score // 25) if score > 0 else min(10, 5 + abs(score) // 25)
    return 0


def compute_confluence_100(
    *,
    setup_name: str,
    result: SetupResult,
    regime: RegimeSnapshot,
    htf: HtfBias,
    direction: str,
    rr: float,
    deriv: dict,
    news: dict,
    mp: tuple[float, float, float] | None,
    price: float,
    settings: Settings | None = None,
) -> Confluence100:
    s = settings or get_settings()
    meta = result.metadata or {}
    bd: dict[str, int] = {}
    factors: list[str] = []

    # 1. Structure (20)
    if _dir_ok(direction, htf.bias) and not htf.in_range_mid:
        bd["structure"] = 20
        factors.append("HTF structure aligned")
    elif setup_name in STRUCTURE_SETUPS:
        bd["structure"] = 10
        factors.append("Structure setup — partial alignment")
    else:
        bd["structure"] = 0

    # 2. Liquidity sweep (15)
    if setup_name in LIQUIDITY_SETUPS or meta.get("sweep") or meta.get("manipulation"):
        bd["liquidity"] = 15 if meta.get("sweep") or setup_name in ("amd_model", "structure_fib_sweep") else 8
        factors.append("Liquidity sweep / AMD")
    else:
        bd["liquidity"] = 0

    # 3. OB / FVG (15)
    if setup_name in ("structure_fib_sweep", "ifvg_reversal", "fvg_retest") or meta.get("ifvg"):
        bd["ob_fvg"] = 15
        factors.append("Order block / FVG zone")
    elif setup_name in STRUCTURE_SETUPS:
        bd["ob_fvg"] = 7
    else:
        bd["ob_fvg"] = 0

    # 4. Liquidation / OI (15)
    fund = deriv.get("funding_regime", "neutral")
    ls = float(deriv.get("long_short_ratio") or 1)
    d_score = 0
    d = direction.upper()
    if fund in ("extreme_long", "crowded_long") and d == "SHORT":
        d_score = 15
        factors.append("Funding crowded long — contrarian short edge")
    elif fund in ("extreme_short", "crowded_short") and d == "LONG":
        d_score = 15
        factors.append("Funding crowded short — contrarian long edge")
    elif deriv.get("liquidation", {}).get("density") in ("high", "medium"):
        d_score = 8
        factors.append("Liq cluster map active")
    elif (d == "LONG" and ls < 0.7) or (d == "SHORT" and ls > 1.4):
        d_score = max(d_score, 8)
    bd["derivatives"] = d_score

    # 5. Funding / flow (15)
    taker = float(deriv.get("taker_buy_sell_ratio") or 1)
    f_score = 0
    if fund != "neutral":
        f_score = 8
    if (d == "LONG" and taker > 1.1) or (d == "SHORT" and taker < 0.9):
        f_score = min(15, f_score + 7)
        factors.append("Taker flow confirming")
    bd["funding_flow"] = f_score

    # 6. News (10)
    np = int(news.get("news_points") or 0)
    ns = int(news.get("sentiment_score") or 0)
    if (d == "LONG" and ns > 20) or (d == "SHORT" and ns < -20):
        np = min(10, np + 3)
    elif (d == "LONG" and ns < -30) or (d == "SHORT" and ns > 30):
        np = 0
        factors.append("News contradicts trade — penalty")
    bd["news"] = np
    if np >= 5:
        factors.append(f"News {news.get('sentiment', 'neutral')}: {news.get('headline', '')[:50]}")

    # 7. Market profile (10)
    if mp and price > 0:
        poc, val, vah = mp
        if price > vah and d == "SHORT":
            bd["profile"] = 10
            factors.append("Above VAH — premium short")
        elif price < val and d == "LONG":
            bd["profile"] = 10
            factors.append("Below VAL — discount long")
        elif abs(price - poc) / price < 0.003:
            bd["profile"] = 5
        elif htf.inside_value_area:
            bd["profile"] = 0
        else:
            bd["profile"] = 5
    else:
        bd["profile"] = 0

    if rr >= max(s.normal_min_rr, 1.5) and result.stop_loss:
        factors.append(f"R:R 1:{rr:.1f} · technical SL")

    total = min(100, sum(bd.values()))
    grade = grade_from_score(total)
    return Confluence100(score=total, breakdown=bd, factors=factors, grade=grade, tier_label=grade)


def apply_options_confluence_boost(conf: Confluence100, options: dict, direction: str) -> Confluence100:
    """Boost score when Delta GEX / whale flow confirms trade direction."""
    if not options.get("available"):
        return conf
    boost = 0
    factors = list(conf.factors)
    bd = dict(conf.breakdown)
    d = direction.upper()
    flow = options.get("options_flow") or {}
    gex = options.get("options") or {}
    bias = flow.get("flow_bias", "neutral")
    if (d == "LONG" and bias == "bullish") or (d == "SHORT" and bias == "bearish"):
        boost += 12
        factors.append("Delta whale flow confirms direction")
    whales = flow.get("whale_blocks") or []
    if any(w.get("source") == "account_fills" for w in whales):
        boost += 8
        factors.append("Large blocks on your Delta account")
    elif whales:
        boost += 5
        factors.append("OTM whale blocks on Delta options chain")
    sign = gex.get("net_gex_sign")
    if (d == "LONG" and sign == "positive") or (d == "SHORT" and sign == "negative"):
        boost += 5
        factors.append("Net GEX supports direction")
    iv = float(gex.get("iv_percentile") or 50)
    if iv < 30:
        boost += 3
        factors.append("IV cheap — options buy edge")
    if boost <= 0:
        return conf
    bd["delta_gex"] = boost
    total = min(100, conf.score + boost)
    grade = grade_from_score(total)
    return Confluence100(score=total, breakdown=bd, factors=factors, grade=grade, tier_label=grade)


def grade_from_score(score: int) -> str:
    if score >= 90:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 70:
        return "B"
    return "NO"


def max_leverage_for_grade(grade: str, settings: Settings | None = None) -> int:
    s = settings or get_settings()
    return {
        "A+": s.grade_a_plus_max_leverage,
        "A": s.grade_a_max_leverage,
        "B": s.grade_b_max_leverage,
    }.get(grade, s.grade_b_max_leverage)


def build_prediction(
    symbol: str,
    direction: str,
    entry: float,
    t1: float,
    deriv: dict,
    htf: HtfBias,
    news: dict,
    score: int,
) -> str:
    base = symbol.replace("USDT", "")
    liq = deriv.get("liquidation") or {}
    above = liq.get("cluster_above", entry * 1.01)
    below = liq.get("cluster_below", entry * 0.99)
    sweep = above if direction == "LONG" else below
    conf = min(95, max(55, score))
    return (
        f"In the next 2–6 hours, {base} likely sweeps {sweep:.4g} then targets {t1:.4g} "
        f"({direction}) — liq map + {htf.bias} HTF + funding {deriv.get('funding_pct_8h', 0):+.3f}%. "
        f"News: {news.get('sentiment', 'neutral')}. Confidence: {conf}%."
    )


def delta_no_trade_reason(
    *,
    score: Confluence100,
    htf: HtfBias,
    direction: str,
    news: dict,
    symbol: str,
    open_positions: int,
    symbol_open: bool,
    deriv: dict | None = None,
    result: SetupResult | None = None,
    settings: Settings | None = None,
) -> str | None:
    s = settings or get_settings()
    sym = symbol.upper()
    is_core = sym in CORE_PAIRS
    min_score = s.alpha_min_score_100_core if is_core else s.alpha_min_score_100
    if score.score < min_score or score.grade == "NO":
        return f"Confluence {score.label} below {min_score} — no signal"
    if htf.inside_value_area and not is_core:
        return "Inside market profile value area — chop, no edge"
    if htf.inside_value_area and is_core and score.score < 68:
        return "Inside market profile value area — chop, no edge"
    ns = int(news.get("sentiment_score") or 0)
    d = direction.upper()
    if (d == "LONG" and ns < -50) or (d == "SHORT" and ns > 50):
        return "News strongly contradicts trade direction"
    if (d == "LONG" and ns < -5 and news.get("sentiment") == "bearish") or (
        d == "SHORT" and ns > 5 and news.get("sentiment") == "bullish"
    ):
        return "News sentiment opposite to trade direction"
    if open_positions >= s.alpha_max_correlated_positions:
        return f"Max {s.alpha_max_correlated_positions} correlated positions open"
    if symbol_open and not is_core:
        return "Active signal open on this pair"

    deriv = deriv or {}
    fund = float(deriv.get("funding_pct_8h") or 0)
    liq = deriv.get("liquidation") or {}
    if abs(fund) < 0.005 and score.breakdown.get("derivatives", 0) < 8:
        if htf.in_range_mid:
            return "Funding neutral + mid-range — no edge"
    if liq.get("density") == "high":
        above = float(liq.get("cluster_above") or 0)
        below = float(liq.get("cluster_below") or 0)
        if above and below and htf.inside_value_area:
            return "Dense liq clusters both sides inside VA — chop"
    if deriv.get("cvd_confirming") is False and not is_core:
        meta = (result.metadata if result else None) or {}
        if not meta.get("sweep"):
            return "CVD diverging from price — no confirmation"
    return None


def grade_cap_reason(grade: str, grade_counts: dict[str, int], settings: Settings | None = None) -> str | None:
    s = settings or get_settings()
    caps = {"A+": s.max_grade_a_plus_per_day, "A": s.max_grade_a_per_day, "B": s.max_grade_b_per_day}
    cap = caps.get(grade)
    if cap is None:
        return None
    if grade_counts.get(grade, 0) >= cap:
        return f"Daily {grade} cap reached ({cap}/day)"
    return None


def _build_structure_analysis(
    setup_name: str, result: SetupResult, htf: HtfBias, direction: str, entry: float, stop: float,
) -> dict:
    meta = result.metadata or {}
    sweep = meta.get("sweep") or setup_name in LIQUIDITY_SETUPS
    sweep_level = meta.get("sweep_level") or meta.get("liquidity_level") or stop
    ob_zone = meta.get("ob_zone") or meta.get("ifvg") or setup_name in STRUCTURE_SETUPS
    return {
        "htf_bias": htf.bias,
        "bos_choch": htf.summary,
        "sweep": "Equal highs/lows swept" if sweep else "No recent sweep",
        "sweep_level": sweep_level,
        "mss": meta.get("mss", "Displacement after sweep" if sweep else "Pending"),
        "entry_zone": f"OB/FVG near {entry:.6g}" if ob_zone else f"Structure entry {entry:.6g}",
        "invalidation": f"Close beyond {stop:.6g}",
    }


def _utc_session_label() -> str:
    h = datetime.now(timezone.utc).hour
    if 0 <= h < 2:
        return "Asia Open — structure setups"
    if 7 <= h < 9:
        return "London Open — volume ramp"
    if 12 <= h < 14:
        return "US Pre-Market — news watch"
    if 13 <= h < 16:
        return "NY Open — highest volatility"
    if 18 <= h < 20:
        return "US Afternoon — continuation"
    return "Overnight — A+ only"


def _integrity_check(signal: dict, conf: Confluence100, deriv: dict, options: dict) -> dict[str, bool]:
    liq = deriv.get("liquidation") or {}
    lev = int(signal.get("leverage") or 1)
    max_lev = int(signal.get("max_leverage_grade") or 3)
    entry = float(signal.get("entry_price") or 0)
    sl = float(signal.get("stop_loss_price") or 0)
    liq_px = float(signal.get("liquidation_price") or 0)
    sl_dist = abs(entry - sl) / entry * 100 if entry else 0
    liq_dist = abs(entry - liq_px) / entry * 100 if entry and liq_px else 99
    return {
        "delta_data": options.get("available", False),
        "binance_data": deriv.get("open_interest_usdt", 0) > 0,
        "news_scored": bool(signal.get("news_headline")),
        "confluence_70_plus": conf.score >= 70,
        "prediction_stated": bool(signal.get("prediction")),
        "technical_sl": sl > 0,
        "leverage_ok": lev <= max_lev,
        "liq_buffer_ok": liq_dist >= sl_dist + 15 if liq_px else True,
        "position_sized": float(signal.get("margin_usdt") or 0) > 0,
        "disclaimer": bool(signal.get("disclaimer")),
    }


def enrich_delta_signal(
    signal: dict,
    *,
    df: pd.DataFrame,
    htf_df: pd.DataFrame,
    setup_name: str,
    result: SetupResult,
    regime: RegimeSnapshot,
    direction: str,
    rr: float,
    funding_signed: float,
    swing_high: float,
    swing_low: float,
) -> tuple[dict, Confluence100, HtfBias, dict]:
    """Full Delta × Binance payload for API + Flutter UI."""
    from app.signals.alpha_engine import layered_targets

    from app.services.delta_exchange import get_options_snapshot

    entry = float(signal.get("entry_price") or 0)
    stop = float(signal.get("stop_loss_price") or 0)
    sym = signal.get("symbol", "")
    mp = profile_levels(df.iloc[-60:]) if len(df) >= 30 else None
    htf_mp = profile_levels(htf_df.iloc[-40:]) if len(htf_df) >= 20 else mp
    htf = htf_bias_smc(htf_df if len(htf_df) >= 20 else df, htf_mp)
    deriv = get_derivatives_snapshot(
        sym, swing_high=swing_high, swing_low=swing_low, price=entry,
        funding_signed_pct=funding_signed, direction=direction,
    )
    options = get_options_snapshot(sym)
    news = news_sentiment_for_symbol(sym)
    conf = compute_confluence_100(
        setup_name=setup_name, result=result, regime=regime, htf=htf, direction=direction,
        rr=rr, deriv=deriv, news=news, mp=mp, price=entry,
    )
    conf = apply_options_confluence_boost(conf, options, direction)
    t1, t2, t3 = layered_targets(entry, stop, direction) if entry and stop else (0, 0, 0)
    prediction = build_prediction(sym, direction, entry, t1, deriv, htf, news, conf.score)
    grade = conf.grade
    max_lev = max_leverage_for_grade(grade)
    if int(signal.get("leverage") or 1) > max_lev:
        signal["leverage"] = max_lev
        signal["grade_leverage_capped"] = True

    poc, val, vah = mp if mp else (0.0, 0.0, 0.0)
    structure = _build_structure_analysis(setup_name, result, htf, direction, entry, stop)
    conf_emoji = "🟢" if conf.score >= 85 else ("🟡" if conf.score >= 75 else "🟠")
    signal.update({
        "engine": "delta_binance_alpha",
        "signal_header": f"🎯 [{grade}] {setup_name.replace('_', ' ').upper()} — {sym} — Binance — {direction}",
        "confluence_score": conf.score,
        "confluence_label": conf.label,
        "confluence_breakdown": conf.breakdown,
        "confluence_factors": conf.factors,
        "confluence_emoji": conf_emoji,
        "signal_grade": grade,
        "tier_label": grade,
        "instrument_type": "USDT Perp",
        "holding_style": "Scalp",
        "prediction": prediction,
        "news_headline": news.get("headline", ""),
        "news_source": news.get("source", ""),
        "news_sentiment": news.get("sentiment", "neutral"),
        "news_sentiment_score": news.get("sentiment_score", 0),
        "news_impact": news.get("impact", "low"),
        "news_effect": "confirming" if _news_confirms(direction, news) else (
            "contradictory" if _news_contradicts(direction, news) else "neutral"
        ),
        "htf_bias": htf.bias,
        "htf_summary": htf.summary,
        "structure_analysis": structure,
        "derivatives": deriv,
        "options_gex": options,
        "market_profile": {"poc": poc, "val": val, "vah": vah, "position": _mp_position(entry, val, vah)},
        "support_price": round(swing_low, 8),
        "resistance_price": round(swing_high, 8),
        "target_3_price": t3,
        "expected_move_pct": round(abs(t1 - entry) / entry * 100, 2) if entry else 0,
        "max_leverage_grade": max_lev,
        "risk_level": "Low" if conf.score >= 85 else ("Medium" if conf.score >= 70 else "High"),
        "invalidation": structure["invalidation"],
        "management_rules": [
            "Move SL to BE when TP1 zone reached",
            "If news breaks against position, reduce size 50%",
            "Trail TP aggressively if liq cluster breached in favor",
        ],
        "disclaimer": (
            "Crypto trading carries substantial risk. Leverage amplifies losses. "
            "Past performance does not guarantee future results. Educational only."
        ),
        "chart_timeframe": "5m",
        "trade_timeframe": "5m",
        "entry_timeframe": "1m",
        "htf_timeframe": "1h",
        "exchange": "Binance USDT Perp",
        "session_label": _utc_session_label(),
        "integrity_check": _integrity_check(signal, conf, deriv, options),
        "delta_keys_active": delta_client.is_configured(),
        "notify": conf.score >= 75 or conf.grade in ("A+", "A"),
        "is_high_priority": conf.score >= 85,
    })
    attach_alpha_report(signal)  # canonical Section 10 — replaces validity_points
    return signal, conf, htf, news


def _mp_position(price: float, val: float, vah: float) -> str:
    if price > vah:
        return "above_vah"
    if price < val:
        return "below_val"
    return "inside_va"


def _news_confirms(direction: str, news: dict) -> bool:
    s = news.get("sentiment", "neutral")
    d = direction.upper()
    return (d == "LONG" and s == "bullish") or (d == "SHORT" and s == "bearish")


def _news_contradicts(direction: str, news: dict) -> bool:
    s = news.get("sentiment", "neutral")
    d = direction.upper()
    return (d == "LONG" and s == "bearish") or (d == "SHORT" and s == "bullish")


def attach_alpha_report(signal: dict) -> dict:
    """Single canonical Section 10 payload — card, chart, and API all use this."""
    signal["alpha_report"] = build_alpha_report(signal)
    signal["validity_points"] = alpha_report_to_lines(signal["alpha_report"])
    return signal


def build_alpha_report(signal: dict) -> dict:
    direction = (signal.get("direction") or "LONG").upper()
    is_straddle = direction == "STRADDLE"
    deriv = signal.get("derivatives") or {}
    liq = deriv.get("liquidation") or {}
    options = signal.get("options_gex") or {}
    gex = (options.get("options") or {}) if options.get("available") else {}
    mp = signal.get("market_profile") or {}
    structure = signal.get("structure_analysis") or {}
    grade = signal.get("signal_grade") or signal.get("tier_label") or "B"
    score = int(signal.get("confluence_score") or signal.get("confidence") or 0)
    entry = float(signal.get("entry_price") or 0)
    move = float(signal.get("target_move_usdt") or 0)
    tp1 = float(signal.get("target_1_price") or 0)
    tp2 = float(signal.get("target_2_price") or 0)
    tp3 = float(signal.get("target_3_price") or 0)
    pos = mp.get("position", "")
    pos_human = {"above_vah": "Above VAH", "below_val": "Below VAL", "inside_va": "Inside VA"}.get(pos, pos)

    trade: dict = {
        "entry": entry,
        "stop_loss": float(signal.get("stop_loss_price") or 0),
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "leverage": signal.get("leverage"),
        "margin_inr": signal.get("margin_inr"),
        "position_inr": signal.get("position_inr"),
        "liquidation_price": float(signal.get("liquidation_price") or 0),
        "invalidation": signal.get("invalidation", ""),
    }
    if is_straddle:
        trade["tp_up"] = tp1
        trade["tp_down"] = tp2
        trade["move_usdt"] = move
        trade["tp1_label"] = f"TP ↑ WIN (+${move:.0f})"
        trade["tp2_label"] = f"TP ↓ WIN (−${move:.0f})"
        trade["straddle_note"] = "Both targets are profit zones — not long vs short bias"

    return {
        "header": signal.get("signal_header", ""),
        "confluence": {
            "score": score,
            "label": signal.get("confluence_label", f"{score}/100"),
            "grade": grade,
            "confidence": int(signal.get("confidence") or score),
            "emoji": signal.get("confluence_emoji", "🟡"),
        },
        "prediction": signal.get("prediction", ""),
        "news": {
            "headline": signal.get("news_headline", ""),
            "source": signal.get("news_source", ""),
            "impact": signal.get("news_impact", "low"),
            "sentiment_score": int(signal.get("news_sentiment_score") or 0),
            "sentiment": signal.get("news_sentiment", "neutral"),
            "effect": signal.get("news_effect", "neutral"),
        },
        "structure": {
            "htf_bias": signal.get("htf_bias") or structure.get("htf_bias", ""),
            "summary": signal.get("htf_summary", ""),
            "sweep": structure.get("sweep", ""),
            "sweep_level": structure.get("sweep_level"),
            "entry_zone": structure.get("entry_zone", ""),
            "invalidation": structure.get("invalidation") or signal.get("invalidation", ""),
        },
        "derivatives": {
            "oi_usdt": deriv.get("open_interest_usdt", 0),
            "oi_change_24h_pct": deriv.get("oi_change_24h_pct", 0),
            "funding_pct_8h": deriv.get("funding_pct_8h", 0),
            "funding_regime": deriv.get("funding_regime", "neutral"),
            "long_short_ratio": deriv.get("long_short_ratio", 1),
            "taker_ratio": deriv.get("taker_buy_sell_ratio", 1),
            "liq_above": liq.get("cluster_above", 0),
            "liq_below": liq.get("cluster_below", 0),
            "liq_density": liq.get("density", "low"),
            "cvd_trend": deriv.get("cvd_trend", "flat"),
            "cvd_confirming": deriv.get("cvd_confirming"),
        },
        "gex": {
            "available": options.get("available", False),
            "zero_gamma": gex.get("zero_gamma"),
            "net_gex_sign": gex.get("net_gex_sign"),
            "call_wall": gex.get("call_wall"),
            "put_wall": gex.get("put_wall"),
            "max_pain": gex.get("max_pain"),
            "iv_percentile": gex.get("iv_percentile"),
            "strategy_hint": options.get("strategy_hint", ""),
            "flow_bias": (options.get("options_flow") or {}).get("flow_bias"),
        },
        "market_profile": {
            "poc": mp.get("poc", 0),
            "vah": mp.get("vah", 0),
            "val": mp.get("val", 0),
            "position": pos_human,
        },
        "trade": trade,
        "meta": {
            "direction": direction,
            "instrument": signal.get("instrument_type", ""),
            "exchange": signal.get("exchange", ""),
            "holding": signal.get("holding_style", ""),
            "risk_level": signal.get("risk_level", ""),
            "setup_label": signal.get("setup_label", ""),
        },
        "management": list(signal.get("management_rules") or []),
        "live_status": signal.get("live_status_message", ""),
        "disclaimer": signal.get("disclaimer", ""),
        "straddle_setup": signal.get("straddle_setup") or {},
    }


def alpha_report_to_lines(report: dict) -> list[str]:
    """Flatten Section 10 report for checklist / legacy validity_points."""
    c = report.get("confluence") or {}
    n = report.get("news") or {}
    s = report.get("structure") or {}
    d = report.get("derivatives") or {}
    g = report.get("gex") or {}
    mp = report.get("market_profile") or {}
    t = report.get("trade") or {}
    m = report.get("meta") or {}
    lines = [
        f"CONFLUENCE {c.get('label', '')} · Grade {c.get('grade', '')} · {m.get('instrument', '')}",
        f"PREDICTION: {report.get('prediction', '')}",
        f"NEWS [{str(n.get('impact', 'low')).upper()}]: {str(n.get('headline', ''))[:100]} · "
        f"{n.get('sentiment', 'neutral')} ({n.get('sentiment_score', 0):+d}) · {n.get('effect', '')}",
        f"STRUCTURE: {s.get('summary', '')}",
        f"DERIVATIVES: OI ${float(d.get('oi_usdt', 0))/1e6:.0f}M ({float(d.get('oi_change_24h_pct', 0)):+.1f}%) · "
        f"Funding {float(d.get('funding_pct_8h', 0)):+.4f}% · L/S {d.get('long_short_ratio', 1)} · "
        f"CVD {d.get('cvd_trend', 'flat')}",
        f"LIQ MAP: Above {d.get('liq_above', 0)} · Below {d.get('liq_below', 0)} · Density {d.get('liq_density', 'low')}",
    ]
    if g.get("available"):
        lines.append(
            f"GEX/DELTA: Zero γ {g.get('zero_gamma')} · {g.get('net_gex_sign')} · "
            f"Call {g.get('call_wall')} · Put {g.get('put_wall')} · Max pain {g.get('max_pain')} · IV {g.get('iv_percentile')}%"
        )
    lines.append(f"PROFILE: POC {mp.get('poc')} · VAH {mp.get('vah')} · VAL {mp.get('val')} · {mp.get('position')}")
    if m.get("direction") == "STRADDLE":
        move = float(t.get("move_usdt") or 0)
        ss = report.get("straddle_setup") or {}
        if ss.get("legs"):
            legs = ss.get("legs") or []
            for leg in legs:
                lines.append(
                    f"{leg.get('side')} {leg.get('type')}: {leg.get('symbol')} · "
                    f"premium {leg.get('premium')} · qty {leg.get('qty', 1)}"
                )
            lines.append(f"Strike {ss.get('strike')} · Expiry {ss.get('expiry')} · Total premium {ss.get('total_premium')}")
        lines.append(
            f"STRADDLE WIN ZONES: Entry {t.get('entry')} · "
            f"TP ↑ {t.get('tp_up')} (+${move:.0f} move up) · "
            f"TP ↓ {t.get('tp_down')} (−${move:.0f} move down) · SL {t.get('stop_loss')}"
        )
    else:
        lines.append(
            f"TRADE: Entry {t.get('entry')} · SL {t.get('stop_loss')} · "
            f"TP1 {t.get('tp1')} · TP2 {t.get('tp2')} · TP3 {t.get('tp3')}"
        )
    lines.append(f"LEVERAGE: {t.get('leverage')}x · Liq {t.get('liquidation_price')}")
    if report.get("disclaimer"):
        lines.append(str(report["disclaimer"]))
    return lines


def _format_validity(signal: dict, conf: Confluence100, htf: HtfBias, deriv: dict, news: dict, options: dict, t1, t2, t3) -> list[str]:
    liq = deriv.get("liquidation") or {}
    mp = signal.get("market_profile") or {}
    gex = (options.get("options") or {}) if options.get("available") else {}
    cvd = deriv.get("cvd_trend", "flat")
    lines = [
        f"CONFLUENCE {conf.label} · Grade {conf.grade} · Binance Perp",
        f"PREDICTION: {signal.get('prediction', '')}",
        f"NEWS [{news.get('impact', 'low').upper()}]: {news.get('headline', '')[:80]} · {news.get('sentiment', 'neutral')} ({news.get('sentiment_score', 0):+d})",
        f"STRUCTURE: {htf.summary}",
        f"DERIVATIVES: OI ${deriv.get('open_interest_usdt', 0)/1e6:.0f}M ({deriv.get('oi_change_24h_pct', 0):+.1f}%) · Funding {deriv.get('funding_pct_8h', 0):+.4f}% · L/S {deriv.get('long_short_ratio', 1)} · CVD {cvd}",
        f"LIQ MAP: Above {liq.get('cluster_above', 0)} · Below {liq.get('cluster_below', 0)} · Density {liq.get('density', 'low')}",
    ]
    if gex:
        lines.append(
            f"GEX/DELTA: Zero γ {gex.get('zero_gamma', 0)} · Call wall {gex.get('call_wall', 0)} · Put wall {gex.get('put_wall', 0)} · Max pain {gex.get('max_pain', 0)}"
        )
    lines.extend([
        f"PROFILE: POC {mp.get('poc', 0)} · VAH {mp.get('vah', 0)} · VAL {mp.get('val', 0)}",
        f"TRADE: Entry {signal.get('entry_price')} · SL {signal.get('stop_loss_price')} · TP1 {t1} · TP2 {t2} · TP3 {t3}",
        f"LEVERAGE: {signal.get('leverage')}x (max {signal.get('max_leverage_grade')}x for grade {conf.grade}) · Liq {signal.get('liquidation_price')}",
        signal.get("disclaimer", ""),
    ])
    return lines


OPTION_SCAN_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def movement_usdt_for_symbol(symbol: str, entry: float, settings: Settings | None = None) -> float:
    """User target: ~$1000 on BTC; scaled for other majors."""
    s = settings or get_settings()
    sym = symbol.upper()
    base_move = float(s.alpha_target_move_usdt or 1000.0)
    if sym == "BTCUSDT":
        return base_move
    if sym == "ETHUSDT":
        return max(35.0, round(base_move * (entry / 77500.0), 1))
    if sym == "PAXGUSDT":
        return max(12.0, round(base_move * 0.012, 1))
    if sym == "SOLUSDT":
        return max(3.0, round(base_move * (entry / 77500.0), 1))
    return max(10.0, round(entry * 0.013, 1))


def straddle_targets(entry: float, move: float) -> tuple[float, float, float]:
    """TP1 = up move, TP2 = down move, TP3 = extended up."""
    return (round(entry + move, 2), round(entry - move, 2), round(entry + move * 1.5, 2))


def scan_delta_options_signals(settings: Settings | None = None) -> list[dict]:
    """Generate Delta Exchange crypto options signals — straddle (long + short) by default."""
    from app.services.crypto_futures_client import futures_client
    from app.services.delta_exchange import get_options_snapshot

    s = settings or get_settings()
    out: list[dict] = []
    for sym in OPTION_SCAN_SYMBOLS:
        try:
            options = get_options_snapshot(sym)
            if not options.get("available"):
                continue
            gex = options.get("options") or {}
            flow = options.get("options_flow") or {}
            spot = float(gex.get("spot") or 0)
            if spot <= 0:
                continue
            candles = futures_client.get_futures_candles(sym, "1h", 48)
            df = futures_client.candles_to_df(candles)
            mp = profile_levels(df.iloc[-40:]) if len(df) >= 30 else None
            htf = htf_bias_smc(df, mp)
            sh, sl = swing_high_low(df, lookback=20) if len(df) >= 25 else (spot * 1.01, spot * 0.99)
            deriv = get_derivatives_snapshot(sym, swing_high=sh, swing_low=sl, price=spot)
            news = news_sentiment_for_symbol(sym)
            bias = flow.get("flow_bias", "neutral")
            call_wall = float(gex.get("call_wall") or spot * 1.02)
            put_wall = float(gex.get("put_wall") or spot * 0.98)
            iv = float(gex.get("iv_percentile") or 50)
            move = movement_usdt_for_symbol(sym, spot, s)
            entry = round(spot, 2)
            straddle_info = options.get("atm_straddle")
            if not straddle_info:
                continue
            poc, val, vah = mp if mp else (0.0, 0.0, 0.0)
            mp_pos = _mp_position(entry, val, vah)

            # Straddle only when IV cheap (Section 9) — skip random/chop signals
            if iv >= 40:
                continue
            if mp_pos == "inside_va":
                continue

            direction = "STRADDLE"
            setup = "delta_straddle"
            strike = float(straddle_info.get("strike") or entry)
            strategy = (
                f"Long Straddle @ {strike:.0f} — BUY call + BUY put · "
                f"win on ±${move:.0f} spot move"
            )
            t1, t2, t3 = straddle_targets(entry, move)
            stop = round(entry * 0.992, 2)

            score = 52
            factors: list[str] = [
                f"BUY 1× call + BUY 1× put @ strike {strike:.0f} (Delta)",
                f"Contracts: {straddle_info['legs'][0]['symbol']} + {straddle_info['legs'][1]['symbol']}",
                f"Total premium ~{straddle_info.get('total_premium')} USDT",
                f"Spot win zones: ↑ {t1:.0f} / ↓ {t2:.0f}",
            ]
            if iv < 30:
                score += 12
                factors.append(f"IV {iv:.0f}% — cheap options (straddle edge)")
            elif iv < 40:
                score += 6
                factors.append(f"IV {iv:.0f}% — acceptable for straddle")
            if bias != "neutral":
                score += 8
                factors.append(f"Whale flow {bias} — expansion either way")
            if delta_client.is_configured():
                score += 5
                factors.append("Delta API key active")
            if any(w.get("source") == "account_fills" for w in (flow.get("whale_blocks") or [])):
                score += 10
                factors.append("Large option blocks on Delta account")
            liq_density = (deriv.get("liquidation") or {}).get("density")
            if liq_density in ("high", "medium"):
                score += 10
                factors.append("Liq clusters both sides — move likely")
            if htf.inside_value_area:
                score -= 15
            if news.get("sentiment_score", 0) and abs(news.get("sentiment_score", 0)) >= 8:
                score += 5
                factors.append(f"News {news.get('sentiment')} — volatility catalyst")
            if score < s.alpha_min_score_100:
                continue
            grade = grade_from_score(score)
            if grade == "NO":
                continue
            base = sym.replace("USDT", "")
            prediction = (
                f"BUY straddle on Delta: {straddle_info['instruction']}. "
                f"In 2–6h, spot wins if ↑ {t1:.0f} (+${move:.0f}) or ↓ {t2:.0f} (−${move:.0f}) from {entry:.0f}. "
                f"Strike {strike:.0f} · Premium ~{straddle_info.get('total_premium')} USDT · IV {iv:.0f}%."
            )
            conf = Confluence100(
                score=min(100, score),
                breakdown={"delta_straddle": score},
                factors=factors,
                grade=grade,
                tier_label=grade,
            )
            sig = {
                "symbol": sym,
                "direction": direction,
                "setup": setup,
                "setup_label": strategy,
                "straddle_setup": {
                    **straddle_info,
                    "tp_spot_up": t1,
                    "tp_spot_down": t2,
                    "entry_spot": entry,
                    "move_usdt": move,
                },
                "entry_price": entry,
                "stop_loss_price": stop,
                "target_1_price": t1,
                "target_2_price": t2,
                "target_3_price": t3,
                "target_move_usdt": move,
                "confidence": min(95, 55 + score // 2),
                "leverage": 1,
                "liquidation_price": 0,
                "category": "major",
                "tier": "A",
                "status": "LIVE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "engine": "delta_binance_alpha",
                "signal_header": f"🎯 [{grade}] STRADDLE — {base} — Delta Options — LONG+SHORT",
                "confluence_score": conf.score,
                "confluence_label": conf.label,
                "confluence_factors": factors,
                "confluence_emoji": "🟢" if score >= 85 else ("🟡" if score >= 75 else "🟠"),
                "signal_grade": grade,
                "instrument_type": "Crypto Options",
                "exchange": "Delta Exchange",
                "holding_style": "Swing",
                "prediction": prediction,
                "news_headline": news.get("headline", ""),
                "news_sentiment": news.get("sentiment", "neutral"),
                "news_sentiment_score": news.get("sentiment_score", 0),
                "news_impact": news.get("impact", "low"),
                "news_effect": "neutral",
                "htf_bias": htf.bias,
                "htf_summary": htf.summary,
                "derivatives": deriv,
                "options_gex": options,
                "market_profile": {"poc": poc, "val": val, "vah": vah, "position": _mp_position(entry, val, vah)},
                "tp_up_price": round(t1, 2),
                "tp_down_price": round(t2, 2),
                "support_price": round(sl, 2),
                "resistance_price": round(sh, 2),
                "max_leverage_grade": 1,
                "risk_level": "Medium",
                "notify": score >= 70,
                "is_high_priority": score >= 85,
                "strategy_tier": "TOP",
                "risk_reward": round(move / max(abs(entry - stop), entry * 0.001), 2),
                "expected_move_pct": round(move / entry * 100, 2) if entry else 0,
                "delta_keys_active": delta_client.is_configured(),
                "disclaimer": "Straddle: max loss = premiums paid if no move. Educational only.",
            }
            attach_alpha_report(sig)
            out.append(sig)
        except Exception:
            logger.exception("Delta options scan failed for %s", sym)
    return out


def _format_straddle_validity(
    signal: dict, conf: Confluence100, htf: HtfBias, deriv: dict, news: dict,
    options: dict, t_up: float, t_down: float, t_ext: float, move: float,
) -> list[str]:
    gex = (options.get("options") or {}) if options.get("available") else {}
    return [
        f"STRADDLE {conf.label} · Grade {conf.grade} · Delta Options",
        f"PREDICTION: {signal.get('prediction', '')}",
        f"ENTRY {signal.get('entry_price')} · TP UP {t_up:.2f} (+${move:.0f}) · TP DOWN {t_down:.2f} (−${move:.0f}) · EXT {t_ext:.2f}",
        f"STRUCTURE: {htf.summary}",
        f"GEX: Zero γ {gex.get('zero_gamma', 0)} · Call wall {gex.get('call_wall', 0)} · Put wall {gex.get('put_wall', 0)}",
        signal.get("disclaimer", ""),
    ]
