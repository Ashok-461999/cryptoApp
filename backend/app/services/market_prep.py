"""Market prep digest when fewer than 5 quality signals — Section 11."""

from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_settings
from app.services.binance_data import binance_data
from app.services.binance_derivatives import get_derivatives_snapshot
from app.services.macro_snapshot import get_macro_snapshot
from app.services.market_news import fetch_market_news


def build_market_prep(signals_today: int = 0) -> dict:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    news = fetch_market_news(20)
    macro = get_macro_snapshot()
    top_news = [
        {
            "title": (i.get("title") or "")[:100],
            "impact": i.get("impact_level", "medium"),
            "sentiment": i.get("sentiment", "neutral"),
            "source": i.get("source", ""),
        }
        for i in (news.get("items") or [])[:3]
    ]

    pairs = []
    watchlist = []
    for sym, label in (("BTCUSDT", "BTC"), ("PAXGUSDT", "GOLD"), ("ETHUSDT", "ETH")):
        try:
            tick = binance_data.get_futures_ticker_24hr(sym)
            if isinstance(tick, dict):
                price = float(tick.get("lastPrice") or 0)
                chg = float(tick.get("priceChangePercent") or 0)
            else:
                price = binance_data.get_price(sym)
                chg = 0.0
            from app.services.crypto_futures_client import futures_client
            from app.signals.market_structure import swing_high_low

            candles = futures_client.get_futures_candles(sym, "1h", 48)
            df = futures_client.candles_to_df(candles)
            sh, sl = swing_high_low(df, lookback=20) if len(df) >= 25 else (price * 1.01, price * 0.99)
            deriv = get_derivatives_snapshot(sym, swing_high=sh, swing_low=sl, price=price)
            trend = "up" if chg > 0.5 else ("down" if chg < -0.5 else "sideways")
            liq = deriv.get("liquidation") or {}
            pairs.append({
                "symbol": sym,
                "label": label,
                "price": price,
                "change_pct_24h": round(chg, 2),
                "trend": trend,
                "funding_pct": deriv["funding_pct_8h"],
                "oi_usdt": deriv.get("open_interest_usdt", 0),
                "liq_above": liq.get("cluster_above", sh),
                "liq_below": liq.get("cluster_below", sl),
            })
            magnet = liq.get("cluster_above", sh) if trend == "up" else liq.get("cluster_below", sl)
            watchlist.append({
                "pair": label,
                "note": f"Awaiting sweep at {magnet:.4g}",
            })
        except Exception:
            continue

    return {
        "generated_at": now.isoformat(),
        "signals_today": signals_today,
        "signal_cap": settings.max_take_signals_per_day,
        "headline": (
            f"No high-probability setups yet ({signals_today}/{settings.max_take_signals_per_day}). "
            "Watching BTC, Gold & ETH for sweep + structure."
        ),
        "macro": macro,
        "top_news": top_news,
        "pairs": pairs,
        "liquidation_landscape": [
            {"label": p["label"], "above": p["liq_above"], "below": p["liq_below"]}
            for p in pairs
        ],
        "watchlist": watchlist[:4],
        "disclaimer": (
            "Crypto trading carries substantial risk. Past performance does not guarantee future results. "
            "Educational analysis only."
        ),
    }
