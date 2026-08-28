import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.signal_tracker import count_signals_today, count_user_takes_today, get_trade_history
from app.signals.crypto_scanner import crypto_scanner

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


class SignalBroadcaster:
    def __init__(self) -> None:
        self._clients: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._prices: dict[str, float] = {}

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        crypto_scanner.subscribe(self._on_scan_update)

    def _on_scan_update(self, _signal: dict) -> None:
        self._schedule(self.broadcast_snapshot())

    def _schedule(self, coro) -> None:
        if self._loop:
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    def on_price(self, symbol: str, price: float) -> None:
        from app.services.signal_tracker import update_on_price

        self._prices[symbol] = price
        closed = update_on_price(symbol, price)
        self._schedule(self._broadcast({"type": "price", "data": {"symbol": symbol, "price": price}}))
        for trade in closed:
            self._schedule(self._broadcast({"type": "trade_closed", "data": trade}))
        if closed:
            self._schedule(self.broadcast_snapshot())

    async def _broadcast(self, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self._clients:
                self._clients.remove(ws)

    async def broadcast_snapshot(self) -> None:
        settings = get_settings()
        await self._broadcast({
            "type": "snapshot",
            "data": {
                "signals": crypto_scanner.get_active_signals(),
                "prices": self._prices,
                "total_scanned": crypto_scanner._last_scan_total,
                "take_count_today": count_signals_today(),
                "user_takes_today": count_user_takes_today(),
                "take_cap_today": settings.max_take_signals_per_day,
                "high_priority_count_today": crypto_scanner.high_priority_count_today,
                "high_priority_cap_today": settings.max_high_priority_signals_per_day,
                "utc_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "recent_closed": _recent_closed_trades(),
            },
        })

    async def connect(self, ws: WebSocket) -> None:
        from app.services.price_sync import sync_tracked_symbols

        await ws.accept()
        self._clients.append(ws)
        sync_tracked_symbols()
        settings = get_settings()
        await ws.send_json({
            "type": "snapshot",
            "data": {
                "signals": crypto_scanner.get_active_signals(),
                "prices": self._prices,
                "total_scanned": crypto_scanner._last_scan_total,
                "take_count_today": count_signals_today(),
                "user_takes_today": count_user_takes_today(),
                "take_cap_today": settings.max_take_signals_per_day,
                "high_priority_count_today": crypto_scanner.high_priority_count_today,
                "high_priority_cap_today": settings.max_high_priority_signals_per_day,
                "utc_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "recent_closed": _recent_closed_trades(),
            },
        })

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)


broadcaster = SignalBroadcaster()


def _recent_closed_trades(limit: int = 10) -> list[dict]:
    from app.services.signal_tracker import get_trade_history

    closed = [t for t in get_trade_history(limit=limit) if t.get("status") in ("WIN", "LOSS", "EXPIRED")]
    return closed[:limit]


@router.websocket("/ws/signals")
async def signals_ws(ws: WebSocket):
    await broadcaster.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        broadcaster.disconnect(ws)
