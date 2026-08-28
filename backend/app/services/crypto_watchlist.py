"""Dynamic crypto futures watchlist — all USDT perpetuals."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import get_settings
from app.services.binance_data import binance_data
from app.signals.position_sizing_crypto import TIER_A_SYMBOLS, TIER_B_MEME, classify_tier

logger = logging.getLogger(__name__)

MAJORS_ALWAYS = TIER_A_SYMBOLS
MEME_KEYWORDS = (
    "PEPE", "BONK", "FLOKI", "SHIB", "MEME", "WIF", "DOGE", "NEIRO", "POPCAT",
    "BOME", "TRUMP", "PNUT", "MOODENG", "GOAT", "TURBO", "BRETT", "1000", "CAT",
    "DOG", "PONKE", "MYRO", "SLERF", "COQ", "LADYS", "AIDOGE", "PEOPLE", "TOSHI",
    "MEW", "CHILLGUY", "FARTCOIN", "AI16Z", "GRIFFAIN", "ZEREBRO", "ACT", "HIPPO",
    "MUBARAK", "TST", "BAN", "ARC", "VINE", "PIPPIN", "SWARMS", "GIGA", "MELANIA",
    "ANIME", "VIRTUAL", "AIXBT", "KOMA", "DEGEN", "BABYDOGE", "CHEEMS", "SUNDOG",
)


@dataclass
class WatchlistSymbol:
    symbol: str
    pair: str
    base: str
    name: str
    tier: str
    volume_24h_usdt: float
    spread_pct: float
    status: str
    category: str
    last_price: float = 0.0
    change_pct_24h: float = 0.0
    abs_change_pct_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "pair": self.pair,
            "base": self.base,
            "name": self.name,
            "tier": self.tier,
            "volume_24h_usdt": round(self.volume_24h_usdt, 0),
            "spread_pct": round(self.spread_pct, 4),
            "status": self.status,
            "category": self.category,
            "last_price": self.last_price,
            "change_pct_24h": round(self.change_pct_24h, 2),
            "abs_change_pct_24h": round(self.abs_change_pct_24h, 2),
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
        }


@dataclass
class WatchlistState:
    symbols: list[WatchlistSymbol] = field(default_factory=list)
    refreshed_at: str = ""
    total_count: int = 0


_watchlist = WatchlistState()


def get_watchlist() -> WatchlistState:
    return _watchlist


def _is_meme_base(base: str, tier: str) -> bool:
    if tier == "D" or base in TIER_B_MEME:
        return True
    return any(k in base.upper() for k in MEME_KEYWORDS)


def _category(base: str, tier: str) -> str:
    if base in MAJORS_ALWAYS or tier == "A":
        return "major"
    if _is_meme_base(base, tier):
        return "meme"
    return "alt"


_CATEGORY_ORDER = {"meme": 0, "major": 1, "alt": 2}
FOCUS_PAIRS = ("BTCUSDT", "PAXGUSDT")


def get_meme_coins() -> list[WatchlistSymbol]:
    wl = get_watchlist()
    if not wl.symbols:
        refresh_watchlist()
        wl = get_watchlist()
    meme = [s for s in wl.symbols if s.category == "meme"]
    meme.sort(key=lambda s: s.volume_24h_usdt, reverse=True)
    return meme


def _trending_score(sym: WatchlistSymbol) -> float:
    """Higher = more trending (volume + absolute 24h move — pumps & dumps)."""
    vol = sym.volume_24h_usdt
    move = abs(sym.change_pct_24h)
    # Favour movers with volume (meme trend)
    return vol * (1.0 + move / 2.5) * (1.0 + min(move, 25) / 25.0)


def get_top_24h_movers(limit: int | None = None) -> list[WatchlistSymbol]:
    """Top Binance USD-M perpetuals by |24h change %| — same as Markets → 24h chg% sort."""
    settings = get_settings()
    cap = limit or settings.top_mover_scan_count
    min_vol = settings.mover_min_volume_usdt
    min_move = settings.mover_min_change_pct
    max_spread = settings.max_spread_pct

    try:
        all_symbols = set(_fetch_perpetual_symbols())
        tickers = binance_data.get_futures_ticker_24hr()
        spreads = binance_data.get_all_book_tickers()
    except Exception:
        logger.exception("Top 24h movers fetch failed")
        return []

    movers: list[WatchlistSymbol] = []
    for sym, t in (tickers.items() if isinstance(tickers, dict) else []):
        if sym not in all_symbols or not sym.endswith("USDT"):
            continue
        change = float(t.get("priceChangePercent") or 0)
        abs_change = abs(change)
        if abs_change < min_move:
            continue
        vol = float(t.get("quoteVolume") or 0)
        if vol < min_vol:
            continue
        spread = spreads.get(sym, 0.5)
        if spread > max_spread * 1.5:
            continue
        base = sym.replace("USDT", "")
        tier = classify_tier(sym)
        movers.append(WatchlistSymbol(
            symbol=sym, pair=sym, base=base, name=base, tier=tier,
            volume_24h_usdt=vol, spread_pct=spread, status="TRADING",
            category="mover" if not _is_meme_base(base, tier) else "meme",
            last_price=float(t.get("lastPrice") or 0),
            change_pct_24h=change,
            abs_change_pct_24h=abs_change,
            high_24h=float(t.get("highPrice") or 0),
            low_24h=float(t.get("lowPrice") or 0),
        ))

    movers.sort(key=lambda s: (s.abs_change_pct_24h, s.volume_24h_usdt), reverse=True)
    return movers[:cap]


def get_top_trending_memes(limit: int | None = None) -> list[WatchlistSymbol]:
    """Legacy alias — now returns top 24h movers (meme keyword filter removed)."""
    return get_top_24h_movers(limit)


def get_scan_symbol_order() -> list[WatchlistSymbol]:
    """Only Binance futures top 24h % movers — no random alts or majors."""
    settings = get_settings()
    if settings.scan_24h_movers_only:
        return get_top_24h_movers()

    wl = get_watchlist()
    if not wl.symbols:
        refresh_watchlist()
        wl = get_watchlist()
    by_pair = {s.pair: s for s in wl.symbols}
    focus = [by_pair[p] for p in FOCUS_PAIRS if p in by_pair]
    trending = [s for s in get_top_24h_movers() if s.pair not in FOCUS_PAIRS]
    trending_pairs = {s.pair for s in trending}
    majors = [
        s for s in wl.symbols
        if s.category == "major" and s.pair not in FOCUS_PAIRS and s.pair not in trending_pairs
    ][:6]
    if settings.prioritize_meme_coins:
        return list(focus) + list(trending) + majors
    rest = [
        s for s in wl.symbols
        if s.pair not in FOCUS_PAIRS
        and s.pair not in trending_pairs
        and s.category != "major"
    ]
    rest.sort(key=lambda s: _CATEGORY_ORDER.get(s.category, 2))
    return list(focus) + list(trending) + majors + rest


def _fetch_perpetual_symbols() -> list[str]:
    info = binance_data.get_futures_exchange_info()
    symbols = []
    for s in info.get("symbols", []):
        if (
            s.get("contractType") == "PERPETUAL"
            and s.get("quoteAsset") == "USDT"
            and s.get("status") == "TRADING"
        ):
            symbols.append(s["symbol"])
    return symbols


def refresh_watchlist() -> WatchlistState:
    global _watchlist
    settings = get_settings()
    min_vol = settings.min_volume_usdt
    meme_min_vol = settings.meme_min_volume_usdt
    max_spread = settings.max_spread_pct

    try:
        all_symbols = _fetch_perpetual_symbols()
        tickers = binance_data.get_ticker_24hr()
        spreads = binance_data.get_all_book_tickers()
    except Exception:
        logger.exception("Failed to fetch watchlist data")
        return _watchlist

    candidates: list[tuple[str, float, dict]] = []
    for sym in all_symbols:
        t = tickers.get(sym, {}) if isinstance(tickers, dict) else {}
        quote_vol = float(t.get("quoteVolume") or 0)
        base = sym.replace("USDT", "")
        tier = classify_tier(sym)
        is_meme = _is_meme_base(base, tier)
        vol_ok = base in MAJORS_ALWAYS or quote_vol >= (meme_min_vol if is_meme else min_vol)
        if vol_ok:
            candidates.append((sym, quote_vol, t))

    candidates.sort(key=lambda x: x[1], reverse=True)

    result: list[WatchlistSymbol] = []
    for sym, quote_vol, t in candidates:
        base = sym.replace("USDT", "")
        tier = classify_tier(sym)
        spread = spreads.get(sym, 0.5)
        is_meme = _is_meme_base(base, tier)

        if base not in MAJORS_ALWAYS:
            min_required = meme_min_vol if is_meme else min_vol
            if quote_vol < min_required:
                continue
            if spread > max_spread * (1.5 if is_meme else 1.0):
                continue

        result.append(
            WatchlistSymbol(
                symbol=sym,
                pair=sym,
                base=base,
                name=base,
                tier=tier,
                volume_24h_usdt=quote_vol,
                spread_pct=spread,
                status="TRADING",
                category=_category(base, tier),
                last_price=float(t.get("lastPrice") or 0),
                change_pct_24h=float(t.get("priceChangePercent") or 0),
                abs_change_pct_24h=abs(float(t.get("priceChangePercent") or 0)),
                high_24h=float(t.get("highPrice") or 0),
                low_24h=float(t.get("lowPrice") or 0),
            )
        )

    _watchlist = WatchlistState(
        symbols=result,
        refreshed_at=datetime.now(timezone.utc).isoformat(),
        total_count=len(result),
    )
    logger.info("Watchlist refreshed: %d symbols (%d meme)", len(result), sum(1 for s in result if s.category == "meme"))
    return _watchlist
