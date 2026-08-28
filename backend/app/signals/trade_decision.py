"""TAKE / NO_TRADE decision engine — SMC scalp strategies with priority tiers."""

from app.config import get_settings
from app.signals.regime import Regime, RegimeSnapshot, setup_allowed_in_regime
from app.signals.schemas import SetupResult

MIN_RR_SCALP = 2.0

# Permanently blocked — proven poor performers in live tracking
PERMANENTLY_DISABLED_SETUPS = frozenset({
    "fvg_retest",
    "orb_breakout",
    "structure_reversal",
    "fibonacci_retrace",
})

# Only these fire unless auto-disabled by analytics
# Best scalp setups for 24h movers (fast in/out on 1m/5m)
TOP_SETUPS = frozenset({
    "order_flow",
    "liquidity_sweep",
    "anchored_vwap",
    "volume_profile",
    "ifvg_reversal",
})
ACTIVE_SETUPS = frozenset({
    "order_flow",
    "liquidity_sweep",
    "anchored_vwap",
    "volume_profile",
    "ifvg_reversal",
    "structure_fib_sweep",
    "amd_model",
})

STRUCTURE_SETUPS = frozenset({
    "structure_fib_sweep", "liquidity_sweep", "amd_model", "ifvg_reversal",
    "order_flow", "anchored_vwap", "volume_profile", "supply_demand",
    "structure_reversal", "fibonacci_retrace",
})

TREND_FOLLOW_SETUPS = frozenset({
    "fibonacci_retrace", "fvg_retest", "orb_breakout", "supply_demand",
})

SETUP_PRIORITY = {
    "order_flow": 0,
    "liquidity_sweep": 1,
    "anchored_vwap": 2,
    "volume_profile": 3,
    "ifvg_reversal": 4,
    "structure_fib_sweep": 5,
    "amd_model": 6,
    "supply_demand": 8,
    "fvg_retest": 99,
    "fibonacci_retrace": 9,
    "structure_reversal": 10,
    "orb_breakout": 11,
}


def _direction_matches_trend(direction: str, trend: str) -> bool:
    if trend == "neutral":
        return True
    if direction == "bullish":
        return trend == "bullish"
    return trend == "bearish"


def compute_take_confidence(
    setup_name: str,
    result: SetupResult,
    regime: RegimeSnapshot,
    category: str = "alt",
) -> int:
    settings = get_settings()
    min_rr = settings.min_rr_for_take
    rr = result.risk_reward or 0.0
    score = 50

    if category == "major":
        score += 8
    elif category in ("meme", "mover"):
        score += 6  # top 24h movers — favourable for scalp

    if regime.regime == Regime.TRENDING and regime.adx >= 25:
        score += 10
    elif regime.regime == Regime.RANGING:
        score += 6 if setup_name in STRUCTURE_SETUPS else 0
    elif regime.regime == Regime.VOLATILE:
        score += 4

    if rr >= 3.0:
        score += 15
    elif rr >= min_rr:
        score += 10
    else:
        score -= 25

    setup_bonus = {
        "order_flow": 18,
        "liquidity_sweep": 16,
        "anchored_vwap": 15,
        "volume_profile": 15,
        "ifvg_reversal": 12,
        "structure_fib_sweep": 10,
        "amd_model": 8,
        "supply_demand": 4,
        "fvg_retest": 0,
        "fibonacci_retrace": 4,
        "structure_reversal": 2,
    }
    score += setup_bonus.get(setup_name, 0)

    meta = result.metadata or {}
    if meta.get("displacement") or meta.get("structure_break"):
        score += 8
    if meta.get("volume_confirmed"):
        score += 5
    if meta.get("ifvg") or meta.get("confluence"):
        score += 6

    if result.fired and setup_allowed_in_regime(setup_name, regime.regime):
        score += 4

    if setup_name in TREND_FOLLOW_SETUPS and result.direction:
        if _direction_matches_trend(result.direction, regime.trend_direction):
            score += 8
        else:
            score -= 15

    return int(max(5, min(95, score)))


def evaluate_trade_decision(
    setup_name: str,
    result: SetupResult,
    regime: RegimeSnapshot,
    category: str = "alt",
) -> dict:
    settings = get_settings()
    min_conf = settings.scalp_min_confidence
    min_rr = settings.min_rr_for_take
    rr = result.risk_reward or 0.0

    if setup_name in PERMANENTLY_DISABLED_SETUPS:
        return {
            "trade_decision": "NO_TRADE",
            "can_take": False,
            "take_confidence": 0,
            "decision_reason": f"{setup_name} blocked — poor live win rate",
        }

    if setup_name not in ACTIVE_SETUPS:
        return {
            "trade_decision": "NO_TRADE",
            "can_take": False,
            "take_confidence": 0,
            "decision_reason": f"{setup_name} not in active strategy set",
        }

    if not result.fired or not result.stop_loss:
        return {
            "trade_decision": "NO_TRADE",
            "can_take": False,
            "take_confidence": 0,
            "decision_reason": "Setup did not fire or missing stop loss",
        }

    confidence = compute_take_confidence(setup_name, result, regime, category)

    if not setup_allowed_in_regime(setup_name, regime.regime):
        return {
            "trade_decision": "NO_TRADE",
            "can_take": False,
            "take_confidence": confidence,
            "decision_reason": f"{setup_name} not suited for {regime.regime.value}",
        }

    if result.direction and regime.trend_direction != "neutral":
        if setup_name not in TOP_SETUPS and not _direction_matches_trend(result.direction, regime.trend_direction):
            return {
                "trade_decision": "NO_TRADE",
                "can_take": False,
                "take_confidence": confidence,
                "decision_reason": f"{result.direction} opposes {regime.trend_direction} trend — skip",
            }

    if regime.regime == Regime.VOLATILE and category == "alt":
        return {
            "trade_decision": "NO_TRADE",
            "can_take": False,
            "take_confidence": confidence,
            "decision_reason": "Volatile chop — skip meme/alt setups",
        }

    if setup_name in TREND_FOLLOW_SETUPS and result.direction:
        if not _direction_matches_trend(result.direction, regime.trend_direction):
            return {
                "trade_decision": "NO_TRADE",
                "can_take": False,
                "take_confidence": confidence,
                "decision_reason": f"{result.direction} opposes {regime.trend_direction} structure",
            }

    if rr < min_rr:
        return {
            "trade_decision": "NO_TRADE",
            "can_take": False,
            "take_confidence": confidence,
            "decision_reason": (
                f"R:R {rr:.2f} below minimum {min_rr} "
                f"(need ₹{settings.target_profit_inr_min:.0f}+ at T1 on ₹{settings.risk_per_trade_inr:.0f} risk)"
            ),
        }

    if confidence < min_conf:
        return {
            "trade_decision": "NO_TRADE",
            "can_take": False,
            "take_confidence": confidence,
            "decision_reason": f"Confidence {confidence}% below {min_conf}%",
        }

    tier = "TOP" if setup_name in TOP_SETUPS else "STD"
    return {
        "trade_decision": "TAKE",
        "can_take": True,
        "take_confidence": confidence,
        "strategy_tier": tier,
        "decision_reason": f"{setup_name} — {result.reason} · {regime.summary}",
    }
