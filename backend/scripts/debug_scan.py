"""Quick scan debug — why signals are empty."""
from app.config import get_settings
from app.services.crypto_watchlist import get_scan_symbol_order, refresh_watchlist
from app.services.crypto_futures_client import futures_client
from app.signals.indicators import ensure_ohlcv
from app.signals.momentum_scalp import _range_context, dip_top_scalp
from app.signals.crypto_scanner import crypto_scanner

refresh_watchlist()
settings = get_settings()
print(f"paused check via scanner only — scanning {settings.top_mover_scan_count} movers")
for sym in get_scan_symbol_order()[:12]:
    candles = futures_client.get_futures_candles(sym.pair, "1m", 60)
    if len(candles) < 20:
        print(sym.pair, "SKIP no candles")
        continue
    df = ensure_ohlcv(futures_client.candles_to_df(candles))
    ctx = _range_context(df)
    hits = dip_top_scalp(df, sym.change_pct_24h)
    if hits:
        for h in hits:
            print(f"  OK {sym.pair} {h.direction} — {h.reason}")
    else:
        pos = f"{ctx['position']*100:.0f}%" if ctx else "no-range"
        print(f"  -- {sym.pair} pos={pos} 24h={sym.change_pct_24h:+.1f}%")

print("--- force_scan ---")
out = crypto_scanner.force_scan()
print(f"new signals: {len(out)}")
for s in out[:5]:
    print(f"  {s.get('symbol')} {s.get('direction')} conf={s.get('confidence')}")
