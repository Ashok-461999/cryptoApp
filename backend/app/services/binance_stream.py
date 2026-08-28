"""Binance Futures WebSocket — live mark prices for active signals."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

import websockets

from app.config import get_settings

logger = logging.getLogger(__name__)


class BinancePriceStream:
    def __init__(self) -> None:
        self._symbols: set[str] = set()
        self._prices: dict[str, float] = {}
        self._task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._on_price: Callable[[str, float], None] | None = None
        self._running = False

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._running = True

    def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    def on_price(self, callback: Callable[[str, float], None]) -> None:
        self._on_price = callback

    def get_price(self, symbol: str) -> float | None:
        return self._prices.get(symbol.upper())

    def get_all_prices(self) -> dict[str, float]:
        return dict(self._prices)

    def set_symbols(self, symbols: list[str]) -> None:
        new_set = {s.upper() for s in symbols if s}
        if new_set == self._symbols:
            return
        self._symbols = new_set
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(self._restart(), self._loop)

    async def _restart(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._symbols:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        settings = get_settings()
        base = settings.binance_fstream_ws_url.rstrip("/")
        streams = "/".join(f"{s.lower()}@markPrice@1s" for s in sorted(self._symbols))
        url = f"{base}/stream?streams={streams}"
        logger.info("Binance WS connecting — %d symbols", len(self._symbols))

        while self._running and self._symbols:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    logger.info("Binance WS connected")
                    async for raw in ws:
                        if not self._running:
                            break
                        self._handle_message(raw)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Binance WS disconnected — retry in 3s")
                await asyncio.sleep(3)
                streams = "/".join(f"{s.lower()}@markPrice@1s" for s in sorted(self._symbols))
                url = f"{base}/stream?streams={streams}"

    def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
            data = msg.get("data") or msg
            sym = (data.get("s") or "").upper()
            price = float(data.get("p") or data.get("c") or 0)
            if sym and price > 0:
                self._prices[sym] = price
                if self._on_price:
                    self._on_price(sym, price)
        except Exception:
            logger.debug("WS parse skip: %s", raw[:120])


price_stream = BinancePriceStream()
