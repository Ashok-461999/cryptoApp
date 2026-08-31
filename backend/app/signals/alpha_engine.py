"""Alpha Engine — confluence, HTF bias, regime gates, and signal enrichment.

Implements institutional rules: min 3 confluence factors, 1:2+ R:R, HTF alignment,
liquidity/AMD validation, funding sentiment, and correlated-position limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.config import Settings, get_settings
from app.signals.market_structure import swing_high_low
from app.signals.regime import Regime, RegimeSnapshot
from app.signals.schemas import SetupResult

LIQUIDITY_SETUPS = frozenset({
    "amd_model", "structure_fib_sweep", "ifvg_reversal", "order_flow", "structure_reversal",
})
STRUCTURE_SETUPS = frozenset({
    "structure_fib_sweep", "amd_model", "structure_reversal", "fibonacci_retrace",
})
ORDER_FLOW_SETUPS = frozenset({"order_flow", "volume_profile", "anchored_vwap"})


@dataclass
class HtfBias:
    bias: str  # bullish | bearish | neutral
    summary: str
    in_range_mid: bool = False
    premium_zone: bool = False
    discount_zone: bool = False


@dataclass
class ConfluenceResult:
    score: int
    max_score: int = 5
    factors: list[str] = field(default_factory=list)
    categories: set[str] = field(default_factory=set)

    @property
    def label(self) -> str:
        return f"{self.score}/{self.max_score}"


def htf_bias(df: pd.DataFrame) -> HtfBias:
    """4H/1H-style bias from higher-timeframe candles."""
    if df is None or len(df) < 30:
        return HtfBias("neutral", "Insufficient HTF data")

    sh, sl = swing_high_low(df, lookback=10)
    price = float(df.iloc[-1]["close"])
    rng = sh - sl
    if rng <= 0:
        return HtfBias("neutral", "Flat HTF range")

    pos = (price - sl) / rng
    in_mid = 0.40 <= pos <= 0.60
    premium = pos >= 0.62
    discount = pos <= 0.38

    ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = df["close"].ewm(span=50, adjust=False).mean().iloc[-1]
    if price > ema20 > ema50:
        bias = "bullish"
        summary = f"HTF bullish — above EMA20/50 ({pos * 100:.0f}% of range)"
    elif price < ema20 < ema50:
        bias = "bearish"
        summary = f"HTF bearish — below EMA20/50 ({pos * 100:.0f}% of range)"
    else:
        bias = "neutral"
        summary = f"HTF neutral — mixed structure ({pos * 100:.0f}% of range)"

    if in_mid:
        summary += " · mid-range (low edge)"
    elif premium:
        summary += " · premium zone"
    elif discount:
        summary += " · discount zone"

    return HtfBias(bias, summary, in_range_mid=in_mid, premium_zone=premium, discount_zone=discount)


def _dir_matches(direction: str, bias: str) -> bool:
    d = direction.upper()
    if bias == "neutral":
        return True
    if d == "LONG":
        return bias == "bullish"
    return bias == "bearish"


def compute_confluence(
    setup_name: str,
    result: SetupResult,
    regime: RegimeSnapshot,
    htf: HtfBias,
    direction: str,
    rr: float,
    settings: Settings | None = None,
) -> ConfluenceResult:
    """5-point Alpha checklist — need min_confluence categories."""
    s = settings or get_settings()
    meta = result.metadata or {}
    factors: list[str] = []
    categories: set[str] = set()

    # [1] HTF bias clear
    if _dir_matches(direction, htf.bias) and not htf.in_range_mid:
        factors.append("HTF bias aligned")
        categories.add("structure")
    elif htf.bias != "neutral" and not htf.in_range_mid:
        factors.append(f"HTF {htf.bias} (counter-trend caution)")

    # [2] Liquidity sweep / AMD
    if setup_name in LIQUIDITY_SETUPS or "liquidity" in str(meta.get("confluence", [])):
        factors.append("Liquidity sweep / AMD")
        categories.add("liquidity")
    if meta.get("sweep") or meta.get("manipulation"):
        factors.append("Sweep confirmed")
        categories.add("liquidity")

    # [3] Structure (MSS/BOS)
    if meta.get("structure_break") or meta.get("choch") or setup_name in STRUCTURE_SETUPS:
        factors.append("Structure shift (MSS/BOS)")
        categories.add("structure")
    if regime.trend_direction != "neutral" and _dir_matches(direction, regime.trend_direction):
        factors.append(f"5m trend {regime.trend_direction}")
        categories.add("structure")

    # [4] Entry zone defined
    if result.entry and result.stop_loss:
        factors.append("Entry zone + technical SL")
        categories.add("execution")

    # Order flow / volume
    if setup_name in ORDER_FLOW_SETUPS or meta.get("volume_confirmed") or meta.get("displacement"):
        factors.append("Order flow / displacement")
        categories.add("order_flow")

    # [5] Risk parameters
    min_rr = max(s.normal_min_rr, 2.0)
    if rr >= min_rr and result.stop_loss:
        factors.append(f"R:R {rr:.1f}:1 · SL beyond sweep")
        categories.add("risk")

    score = min(5, len([f for f in factors if "caution" not in f.lower()]))
    if len(categories) >= 3:
        score = max(score, min(5, len(categories)))

    return ConfluenceResult(score=score, factors=factors, categories=categories)


def funding_blocks_trade(
    direction: str,
    funding_signed_pct: float,
    settings: Settings | None = None,
) -> str | None:
    """Directional funding filter — crowded side caution."""
    s = settings or get_settings()
    extreme = s.max_funding_extreme_pct
    if abs(funding_signed_pct) < extreme:
        return None
    d = direction.upper()
    if funding_signed_pct > extreme and d == "LONG":
        return f"Funding +{funding_signed_pct:.3f}% — crowded longs at resistance"
    if funding_signed_pct < -extreme and d == "SHORT":
        return f"Funding {funding_signed_pct:.3f}% — crowded shorts at support"
    return None


def alpha_no_trade_reason(
    *,
    setup_name: str,
    result: SetupResult,
    regime: RegimeSnapshot,
    htf: HtfBias,
    direction: str,
    rr: float,
    spread_pct: float,
    funding_signed_pct: float,
    open_positions: int,
    symbol_has_open: bool,
    settings: Settings | None = None,
) -> str | None:
    """Return reason string if Alpha Engine rejects the setup."""
    s = settings or get_settings()
    conf = compute_confluence(setup_name, result, regime, htf, direction, rr, s)

    if spread_pct > s.max_spread_pct:
        return f"Spread {spread_pct:.2f}% > {s.max_spread_pct}% — poor execution"
    if htf.in_range_mid:
        return "HTF mid-range (40–60%) — no edge"
    if conf.score < s.alpha_min_confluence_score:
        return f"Confluence {conf.label} — need {s.alpha_min_confluence_score}+ factors"
    if len(conf.categories) < s.alpha_min_confluence_categories:
        return f"Only {len(conf.categories)} confluence categories — need {s.alpha_min_confluence_categories}+"
    if rr < max(s.normal_min_rr, 2.0):
        return f"R:R {rr:.2f} below minimum 1:2"
    if open_positions >= s.alpha_max_correlated_positions:
        return f"Max {s.alpha_max_correlated_positions} correlated positions open"
    if symbol_has_open:
        return "Active signal still open on this pair"
    if regime.regime == Regime.RANGING and conf.score < s.alpha_ranging_min_confluence:
        return f"Ranging market — confluence {conf.label} below {s.alpha_ranging_min_confluence}"
    fund_reason = funding_blocks_trade(direction, funding_signed_pct, s)
    if fund_reason:
        return fund_reason
    if not _dir_matches(direction, htf.bias) and htf.bias != "neutral" and conf.score < 4:
        return f"Counter HTF {htf.bias} bias — insufficient confluence ({conf.label})"
    return None


def layered_targets(
    entry: float,
    stop: float,
    direction: str,
) -> tuple[float, float, float]:
    """TP1 2R (50%), TP2 3R (30%), TP3 trail zone 4R (20%)."""
    risk = abs(entry - stop)
    sign = 1 if direction.upper() == "LONG" else -1
    return (
        entry + sign * risk * 2.0,
        entry + sign * risk * 3.0,
        entry + sign * risk * 4.0,
    )


def loss_cooldown_risk_multiplier(settings: Settings | None = None) -> float:
    """After SL hits, next N signals use reduced risk (0.5%)."""
    s = settings or get_settings()
    from app.services.signal_tracker import recent_sl_hit_count

    hits = recent_sl_hit_count(s.loss_cooldown_after_sl)
    if hits >= s.loss_cooldown_after_sl:
        return s.loss_cooldown_risk_multiplier
    return 1.0


def enrich_alpha_payload(
    signal: dict,
    *,
    htf: HtfBias,
    confluence: ConfluenceResult,
    funding_signed_pct: float,
) -> dict:
    """Attach Alpha Engine fields — shown in existing validity_points / metadata."""
    direction = (signal.get("direction") or "").upper()
    entry = float(signal.get("entry_price") or 0)
    stop = float(signal.get("stop_loss_price") or 0)
    t1, t2, t3 = layered_targets(entry, stop, direction) if entry and stop else (0, 0, 0)

    signal["alpha_confluence_score"] = confluence.score
    signal["alpha_confluence_label"] = confluence.label
    signal["alpha_confluence_factors"] = confluence.factors
    signal["htf_bias"] = htf.bias
    signal["htf_summary"] = htf.summary
    signal["funding_signed_pct"] = round(funding_signed_pct, 4)
    signal["target_3_price"] = t3
    signal["tp1_pct"] = 50
    signal["tp2_pct"] = 30
    signal["tp3_pct"] = 20
    signal["risk_level"] = "Low" if confluence.score >= 4 else ("Medium" if confluence.score >= 3 else "High")
    signal["invalidation"] = f"Close beyond SL {stop:.6g} or HTF bias flips"
    signal["management_notes"] = (
        "Move SL to breakeven at 1:1 R:R · Trail after TP1 (2R) · "
        "Past performance does not guarantee future results."
    )
    signal["chart_timeframe"] = "5m"
    signal["trade_timeframe"] = "5m"
    signal["entry_timeframe"] = "1m"
    signal["htf_timeframe"] = "1h"

    rr = signal.get("risk_reward", 2)
    signal["validity_points"] = [
        f"🎯 {direction} — {signal.get('setup', '')} · Confluence {confluence.label}",
        f"📈 HTF: {htf.summary}",
        f"🧹 Setup: {signal.get('decision_reason', '')}",
        f"📍 Entry {entry:.6g} · SL {stop:.6g} · R:R 1:{rr}",
        f"✅ TP1 (50%): {t1:.6g} · TP2 (30%): {t2:.6g} · TP3 (20%): {t3:.6g}",
        f"📏 Risk {signal.get('risk_percent', 1)}% · Funding {funding_signed_pct:+.4f}%",
        f"⚠️ {signal.get('invalidation', '')}",
        f"💡 {signal.get('management_notes', '')}",
        f"Backtest: {signal.get('backtest_win_rate', 0)}% WR ({signal.get('backtest_samples', 0)} samples)",
    ]
    return signal
