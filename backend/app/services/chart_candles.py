"""Chart candles — Binance intervals + synthetic scalp bars (1s/5s/10s from 1m)."""

from __future__ import annotations

from app.services.binance_data import binance_data

BINANCE_INTERVALS = frozenset({"1m", "3m", "5m", "15m", "1h", "4h", "1d"})
SCALP_SECONDS = {1, 5, 10}


def _synthetic_from_1m(candles_1m: list[dict], seconds: int, limit: int) -> list[dict]:
    """Split each 1m candle into smaller scalp bars (approximation for UI)."""
    if seconds not in SCALP_SECONDS or not candles_1m:
        return candles_1m[-limit:]

    parts = max(1, 60 // seconds)
    out: list[dict] = []
    for bar in candles_1m:
        o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
        vol = float(bar.get("volume") or 0) / parts
        ts = int(bar.get("timestamp") or 0)
        step_ms = seconds * 1000
        for i in range(parts):
            frac0 = i / parts
            frac1 = (i + 1) / parts
            open_p = o + (c - o) * frac0
            close_p = o + (c - o) * frac1
            high_p = max(open_p, close_p, h * (1 - frac0) + h * frac1 * 0.01)  # stay inside parent range
            low_p = min(open_p, close_p, l)
            high_p = min(h, max(open_p, close_p, high_p))
            low_p = max(l, min(open_p, close_p, low_p))
            out.append({
                "timestamp": ts + i * step_ms,
                "open": round(open_p, 8),
                "high": round(high_p, 8),
                "low": round(low_p, 8),
                "close": round(close_p, 8),
                "volume": vol,
            })
    return out[-limit:]


def get_chart_candles(symbol: str, interval: str, limit: int = 120) -> tuple[list[dict], str]:
    """Return candles and resolved interval label."""
    iv = interval.lower().strip()
    if iv.endswith("s") and iv[:-1].isdigit():
        sec = int(iv[:-1])
        if sec in SCALP_SECONDS:
            need_1m = max(20, (limit * sec) // 60 + 5)
            base = binance_data.get_klines(symbol, "1m", min(500, need_1m))
            return _synthetic_from_1m(base, sec, limit), f"{sec}s"
    if iv in BINANCE_INTERVALS:
        return binance_data.get_klines(symbol, iv, limit), iv
    return binance_data.get_klines(symbol, "5m", limit), "5m"
