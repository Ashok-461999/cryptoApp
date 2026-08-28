from fastapi import APIRouter, Query

from app.config import get_settings
from app.services.binance_data import binance_data
from app.services.chart_candles import get_chart_candles
from app.services.crypto_futures_client import futures_client
from app.services.crypto_watchlist import get_meme_coins, get_movers_cache_meta, get_top_24h_movers, get_watchlist, refresh_top_movers, refresh_watchlist
from app.services.focus_tracker import get_btc_gold_tracker
from app.services.mover_tracker import attach_mover_tracker, refresh_mover_trackers
from app.services.signal_tracker import get_today_trades_map
from app.signals.crypto_scanner import crypto_scanner

router = APIRouter(prefix="/crypto", tags=["crypto"])

_FOCUS_SYMBOLS = frozenset({"BTCUSDT", "PAXGUSDT"})

_MARKET_HIGHLIGHTS = [
    ("BTCUSDT", "BTC", "major", "🟡"),
    ("PAXGUSDT", "GOLD", "major", "🥇"),
    ("ETHUSDT", "ETH", "major", "💎"),
    ("BNBUSDT", "BNB", "major", "🔶"),
    ("SOLUSDT", "SOL", "alt", "🟣"),
]


def _active_signals_for_symbol(symbol: str) -> list[dict]:
    """Live signals with entry / SL / target for chart lines."""
    sym = symbol.upper()
    rows: list[dict] = []
    for s in crypto_scanner.get_active_signals():
        if (s.get("symbol") or "").upper() != sym:
            continue
        rows.append({
            "direction": s.get("direction"),
            "setup": s.get("setup"),
            "entry_price": s.get("entry_price"),
            "stop_loss_price": s.get("stop_loss_price"),
            "target_1_price": s.get("target_1_price"),
            "confidence": s.get("confidence"),
            "ref_status": s.get("ref_status"),
            "ref_pnl_inr": s.get("ref_pnl_inr"),
            "live_pnl_inr": s.get("live_pnl_inr"),
            "decision_reason": s.get("decision_reason"),
            "validity_points": s.get("validity_points") or [],
        })
    rows.sort(key=lambda x: -(x.get("confidence") or 0))
    return rows


@router.get("/candles")
def get_candles(
    symbol: str = Query(..., description="e.g. BTCUSDT"),
    interval: str = Query("5m", description="1m, 3m, 5m, 15m, 1h, 4h, 1d, 1s, 5s, 10s"),
    limit: int = Query(120, ge=20, le=500),
):
    """OHLCV candles for trading chart — Binance + synthetic scalp intervals."""
    candles, resolved = get_chart_candles(symbol.upper(), interval, limit)
    return {
        "symbol": symbol.upper(),
        "interval": resolved,
        "candles": candles,
        "count": len(candles),
    }


@router.get("/markets")
def get_market_overview():
    """BTC, ETH, GOLD + meme sentiment strip for home/markets screen."""
    settings = get_settings()
    tickers = binance_data.get_ticker_24hr()
    trade_map = get_today_trades_map()
    highlights = []
    for sym, base, cat, icon in _MARKET_HIGHLIGHTS:
        t = tickers.get(sym, {}) if isinstance(tickers, dict) else {}
        change = float(t.get("priceChangePercent") or 0)
        price = float(t.get("lastPrice") or t.get("weightedAvgPrice") or 0)
        highlights.append({
            "symbol": sym,
            "base": base,
            "icon": icon,
            "category": cat,
            "last_price": price,
            "change_pct_24h": round(change, 2),
            "sentiment": "bullish" if change >= 0 else "bearish",
            "volume_24h": float(t.get("quoteVolume") or 0),
            "signals": _active_signals_for_symbol(sym),
            "is_focus": sym in _FOCUS_SYMBOLS,
        })

    meme_coins = []
    bullish = bearish = 0
    mover_source = get_top_24h_movers() if get_settings().scan_24h_movers_only else get_meme_coins()[:50]
    for s in mover_source[:50]:
        d = s.to_dict()
        ch = float(d.get("change_pct_24h") or 0)
        if ch >= 0:
            bullish += 1
        else:
            bearish += 1
        trade = trade_map.get(s.symbol)
        if trade:
            d["trade_id"] = trade.get("id")
            d["trade_status"] = trade.get("outcome") or trade.get("status")
        else:
            d["trade_status"] = None
        d["signals"] = _active_signals_for_symbol(s.symbol)
        d = attach_mover_tracker(d, s)
        meme_coins.append(d)

    total = bullish + bearish or 1
    focus_tracker = get_btc_gold_tracker()
    tracker_map = {t["symbol"]: t for t in focus_tracker}
    focus = [h for h in highlights if h.get("is_focus")]
    for h in focus:
        t = tracker_map.get(h.get("symbol"))
        if t:
            h["tracker"] = t
            h["chart"] = t.get("chart")
            h["news_context"] = t.get("news_context")
    other_highlights = [h for h in highlights if not h.get("is_focus")]
    return {
        "focus": focus,
        "focus_tracker": focus_tracker,
        "highlights": other_highlights,
        "coins": meme_coins,
        "meme_count": len(meme_coins),
        "sentiment": {
            "bullish_pct": round(bullish / total * 100, 1),
            "bearish_pct": round(bearish / total * 100, 1),
            "bullish_count": bullish,
            "bearish_count": bearish,
        },
        "tracking": _tracking_block(),
        "levels_refresh_minutes": settings.mover_levels_refresh_minutes,
        "exchange": "binance_futures",
    }


def _trade_outcome(t: dict) -> str:
    return t.get("outcome") or t.get("status") or ""


def _tracking_block() -> dict:
    settings = get_settings()
    trade_map = get_today_trades_map()
    today_trades = list(trade_map.values())
    return {
        "today_total": len(today_trades),
        "cap": settings.max_take_signals_per_day if settings.max_take_signals_per_day > 0 else "unlimited",
        "open": sum(1 for t in today_trades if t.get("status") == "OPEN"),
        "wins": sum(1 for t in today_trades if _trade_outcome(t) == "WIN"),
        "losses": sum(1 for t in today_trades if _trade_outcome(t) == "LOSS"),
        "signals_today": crypto_scanner._take_count_today,
    }


@router.get("/movers")
def get_24h_movers(refresh: bool = False):
    """Top Binance USD-M futures by 24h change % — same as Markets tab sort."""
    if refresh:
        refresh_top_movers(force=True)
    settings = get_settings()
    trade_map = get_today_trades_map()
    movers = []
    for s in get_top_24h_movers():
        d = s.to_dict()
        trade = trade_map.get(s.symbol)
        if trade:
            d["trade_id"] = trade.get("id")
            d["trade_status"] = trade.get("outcome") or trade.get("status")
            d["trade_pnl_inr"] = trade.get("pnl_inr", 0)
        else:
            d["trade_status"] = None
        movers.append(d)
    cache = get_movers_cache_meta()
    return {
        "movers": movers,
        "count": len(movers),
        "scan_only_movers": settings.scan_24h_movers_only,
        "top_count": settings.top_mover_scan_count,
        "refreshed_at": cache.get("refreshed_at", ""),
        "refresh_every_hours": cache.get("next_refresh_hours", settings.mover_refresh_hours),
        "exchange": "binance_futures",
        "sort": "volatility_score_desc",
    }


@router.get("/meme")
def get_meme_watchlist(refresh: bool = False):
    """All meme coins with 24h return (Binance-style) + today's trade status."""
    if refresh:
        refresh_watchlist()
    settings = get_settings()
    trade_map = get_today_trades_map()
    coins = []
    for s in get_meme_coins():
        d = s.to_dict()
        trade = trade_map.get(s.symbol)
        if trade:
            d["trade_id"] = trade.get("id")
            d["trade_status"] = trade.get("outcome") or trade.get("status")
            d["trade_pnl_inr"] = trade.get("pnl_inr", 0)
            d["entry_price"] = trade.get("entry_price")
            d["close_reason"] = trade.get("close_reason")
        else:
            d["trade_status"] = None
        coins.append(d)

    today_trades = list(trade_map.values())
    wins = sum(1 for t in today_trades if _trade_outcome(t) == "WIN")
    losses = sum(1 for t in today_trades if _trade_outcome(t) == "LOSS")
    open_n = sum(1 for t in today_trades if t.get("status") == "OPEN")

    return {
        "coins": coins,
        "meme_count": len(coins),
        "tracking": {
            "today_total": len(today_trades),
            "cap": settings.max_take_signals_per_day if settings.max_take_signals_per_day > 0 else "unlimited",
            "open": open_n,
            "wins": wins,
            "losses": losses,
            "signals_today": crypto_scanner._take_count_today,
        },
        "refreshed_at": get_watchlist().refreshed_at,
        "exchange": "binance_futures",
    }


@router.get("/watchlist")
def get_crypto_watchlist(refresh: bool = False):
    """All scanned USDT perpetual symbols with tier + volume."""
    wl = refresh_watchlist() if refresh else get_watchlist()
    if not wl.symbols:
        wl = refresh_watchlist()
    return {
        "instruments": [s.to_dict() for s in wl.symbols],
        "total_count": wl.total_count,
        "refreshed_at": wl.refreshed_at,
        "exchange": "binance_futures",
    }
