"""Section 3C — prediction tracking at 2h and 6h."""

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


def update_prediction_status(signal: dict, price: float) -> dict:
    """Attach prediction_check fields based on signal age."""
    issued = _parse_ts(signal.get("timestamp"))
    if not issued or price <= 0:
        return signal

    entry = float(signal.get("entry_price") or 0)
    t1 = float(signal.get("target_1_price") or 0)
    direction = (signal.get("direction") or "LONG").upper()
    age_h = (datetime.now(timezone.utc) - issued).total_seconds() / 3600

    if entry <= 0:
        return signal

    progress = 0.0
    if t1 > 0:
        total = abs(t1 - entry)
        moved = abs(price - entry) if direction == "LONG" else abs(entry - price)
        progress = min(100, moved / total * 100) if total > 0 else 0

    on_track = progress >= 40
    status = {
        "issued_at": issued.isoformat(),
        "target_price": t1,
        "progress_pct": round(progress, 1),
        "on_track": on_track,
    }

    if age_h >= 2:
        status["check_2h"] = (
            f"Prediction Check — Price at {price:.4g}. "
            f"{'On track' if on_track else 'Off track'} ({progress:.0f}% to TP1)."
        )
    if age_h >= 6:
        hit = (direction == "LONG" and price >= t1) or (direction == "SHORT" and price <= t1)
        partial = progress >= 60 and not hit
        resolution = "Hit" if hit else ("Partial" if partial else "Miss")
        status["check_6h"] = f"Prediction Resolution — {resolution}. Progress {progress:.0f}% to TP1."

    signal["prediction_status"] = status
    return signal
