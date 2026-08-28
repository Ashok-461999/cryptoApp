"""Keep Binance WS subscribed to all symbols we need to track."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def sync_tracked_symbols(extra: list[str] | None = None) -> list[str]:
    """Subscribe price stream to open trades + active signals (+ optional extras)."""
    from app.services.binance_stream import price_stream
    from app.services.signal_tracker import get_open_trades
    from app.signals.crypto_scanner import crypto_scanner

    symbols: set[str] = {s.upper() for s in (extra or []) if s}
    symbols.update(t["symbol"] for t in get_open_trades() if t.get("symbol"))
    symbols.update(
        s["symbol"] for s in crypto_scanner.get_active_signals() if s.get("symbol")
    )
    ordered = sorted(symbols)
    price_stream.set_symbols(ordered)
    logger.debug("Price sync — tracking %d symbols", len(ordered))
    return ordered
