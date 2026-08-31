"""Quick historical gate — only emit signals that backtest positively on recent bars."""

from __future__ import annotations

import pandas as pd

from app.config import Settings, get_settings


def passes_backtest_gate(
    entry_df: pd.DataFrame,
    direction: str,
    entry: float,
    stop: float,
    target: float,
    settings: Settings | None = None,
) -> tuple[bool, dict]:
    """
    Walk recent 1m bars: count how often a similar SL/TP distance would have won
    within the next few candles. Requires min win rate before live signal.
    """
    s = settings or get_settings()
    if entry_df is None or len(entry_df) < 30:
        return False, {"reason": "not enough bars", "samples": 0}

    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0 or reward <= 0:
        return False, {"reason": "invalid levels", "samples": 0}

    rr = reward / risk
    lookback = min(s.backtest_lookback_bars, len(entry_df) - 8)
    forward = max(3, s.scalp_holding_minutes)
    wins = losses = 0
    d = direction.upper()

    highs = entry_df["high"].astype(float).values
    lows = entry_df["low"].astype(float).values
    closes = entry_df["close"].astype(float).values

    start = max(15, len(closes) - lookback)
    for i in range(start, len(closes) - forward - 1):
        e = float(closes[i])
        if d == "LONG":
            sl_p = e - risk
            tp_p = e + risk * rr
            outcome = None
            for j in range(i + 1, min(i + forward + 1, len(closes))):
                if lows[j] <= sl_p:
                    outcome = "loss"
                    break
                if highs[j] >= tp_p:
                    outcome = "win"
                    break
        else:
            sl_p = e + risk
            tp_p = e - risk * rr
            outcome = None
            for j in range(i + 1, min(i + forward + 1, len(closes))):
                if highs[j] >= sl_p:
                    outcome = "loss"
                    break
                if lows[j] <= tp_p:
                    outcome = "win"
                    break
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1

    samples = wins + losses
    meta = {
        "wins": wins,
        "losses": losses,
        "samples": samples,
        "win_rate": round(wins / samples * 100, 1) if samples else 0.0,
    }
    if samples < s.backtest_min_samples:
        meta["reason"] = f"need {s.backtest_min_samples}+ samples, got {samples}"
        return False, meta
    if meta["win_rate"] < s.backtest_min_win_rate:
        meta["reason"] = f"win rate {meta['win_rate']}% < {s.backtest_min_win_rate}%"
        return False, meta
    meta["reason"] = "backtest passed"
    return True, meta
