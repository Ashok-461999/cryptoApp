"""Section 12 — post-signal live management status."""

from __future__ import annotations

from datetime import datetime, timezone


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def compute_live_management(signal: dict, price: float) -> dict:
    """Return live status emoji + message for active signals."""
    direction = (signal.get("direction") or "LONG").upper()
    entry = float(signal.get("entry_price") or 0)
    sl = float(signal.get("stop_loss_price") or 0)
    t1 = float(signal.get("target_1_price") or 0)
    if entry <= 0 or price <= 0:
        return {"status": "MONITORING", "emoji": "🟢", "message": "ACTIVE — Monitoring structure, funding, news"}

    at_sl = (direction == "LONG" and price <= sl) or (direction == "SHORT" and price >= sl)
    at_tp1 = (direction == "LONG" and price >= t1) or (direction == "SHORT" and price <= t1)
    pnl_pct = ((price - entry) / entry * 100) if direction == "LONG" else ((entry - price) / entry * 100)

    deriv = signal.get("derivatives") or {}
    cvd = deriv.get("cvd_trend", deriv.get("cvd_bias", "flat"))
    news_effect = signal.get("news_effect", "neutral")

    if at_sl:
        return {"status": "SL_HIT", "emoji": "❌", "message": "SL HIT — Cooldown: next signals at 50% size"}
    if at_tp1:
        return {"status": "TP1_HIT", "emoji": "✅", "message": "TP1 — Book 50%, SL to breakeven"}

    if news_effect == "contradictory":
        return {"status": "NEWS_FLIP", "emoji": "🚨", "message": "NEWS FLIP — Reduce 50% or exit"}

    if direction == "LONG" and cvd == "falling" and pnl_pct > 0:
        return {"status": "CVD_WARN", "emoji": "⚠️", "message": "HIDDEN SELLING — CVD diverging, consider partial"}
    if direction == "SHORT" and cvd == "rising" and pnl_pct > 0:
        return {"status": "CVD_WARN", "emoji": "⚠️", "message": "HIDDEN BUYING — CVD diverging, consider partial"}

    if pnl_pct >= 0.5:
        return {"status": "ON_TRACK", "emoji": "📈", "message": "ON TRACK — Structure + flow confirming"}
    if pnl_pct <= -0.3:
        return {"status": "DANGER", "emoji": "🚨", "message": "DANGER — Tighten SL now"}

    issued = _parse_ts(signal.get("timestamp"))
    if issued:
        age_h = (datetime.now(timezone.utc) - issued).total_seconds() / 3600
        pred = signal.get("prediction_status") or {}
        if age_h >= 2 and not pred.get("check_2h"):
            return {"status": "PRED_CHECK", "emoji": "🔮", "message": f"Prediction check — price {price:.4g}, on track at +{pnl_pct:.2f}%"}

    return {"status": "ACTIVE", "emoji": "🟢", "message": "ACTIVE — Monitoring structure, funding, news"}
