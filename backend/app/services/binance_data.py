"""Binance public market data via data-api.binance.vision (spot /api/v3)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

INTERVAL_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}


def _data_base() -> str:
    return get_settings().binance_data_base_url.rstrip("/")


def _futures_base() -> str:
    return get_settings().binance_futures_base_url.rstrip("/")


def normalize_pair(symbol: str) -> str:
    return symbol if symbol.endswith("USDT") else f"{symbol}USDT"


class BinanceDataClient:
    """Market data from https://data-api.binance.vision (no API key)."""

    def get_klines(
        self, symbol: str, interval: str = "5m", limit: int = 120,
    ) -> list[dict[str, Any]]:
        pair = normalize_pair(symbol)
        iv = INTERVAL_MAP.get(interval, "5m")
        try:
            r = httpx.get(
                f"{_data_base()}/api/v3/klines",
                params={"symbol": pair, "interval": iv, "limit": limit},
                timeout=20,
            )
            r.raise_for_status()
            return [
                {
                    "timestamp": row[0],
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
                for row in r.json()
            ]
        except Exception:
            logger.exception("Vision klines failed for %s", pair)
            return []

    def get_price(self, symbol: str) -> float:
        pair = normalize_pair(symbol)
        try:
            r = httpx.get(
                f"{_data_base()}/api/v3/ticker/price",
                params={"symbol": pair},
                timeout=10,
            )
            r.raise_for_status()
            return float(r.json().get("price") or 0)
        except Exception:
            logger.exception("Vision price failed for %s", pair)
            return 0.0

    def get_ticker_24hr(self, symbol: str | None = None) -> dict[str, dict] | dict:
        """Single symbol or all 24hr tickers keyed by symbol."""
        try:
            params = {"symbol": normalize_pair(symbol)} if symbol else None
            r = httpx.get(f"{_data_base()}/api/v3/ticker/24hr", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if symbol:
                return data
            return {t["symbol"]: t for t in data}
        except Exception:
            logger.exception("Vision 24hr ticker failed")
            return {} if not symbol else {}

    def get_depth(self, symbol: str, limit: int = 100) -> dict[str, Any]:
        pair = normalize_pair(symbol)
        try:
            r = httpx.get(
                f"{_data_base()}/api/v3/depth",
                params={"symbol": pair, "limit": limit},
                timeout=15,
            )
            r.raise_for_status()
            return r.json()
        except Exception:
            logger.exception("Vision depth failed for %s", pair)
            return {"bids": [], "asks": []}

    def get_spread_pct(self, symbol: str, limit: int = 100) -> float:
        """Spread % from order book depth."""
        depth = self.get_depth(symbol, limit=limit)
        bids = depth.get("bids") or []
        asks = depth.get("asks") or []
        if not bids or not asks:
            return 999.0
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2
        if mid <= 0:
            return 999.0
        return (best_ask - best_bid) / mid * 100

    def get_all_book_tickers(self) -> dict[str, float]:
        """Spread % for all symbols from bookTicker."""
        spreads: dict[str, float] = {}
        try:
            r = httpx.get(f"{_data_base()}/api/v3/ticker/bookTicker", timeout=30)
            r.raise_for_status()
            for item in r.json():
                sym = item.get("symbol", "")
                bid = float(item.get("bidPrice") or 0)
                ask = float(item.get("askPrice") or 0)
                mid = (bid + ask) / 2 if bid and ask else 0
                spreads[sym] = ((ask - bid) / mid * 100) if mid > 0 else 999.0
        except Exception:
            logger.exception("Vision bookTicker failed")
        return spreads

    def get_exchange_info(self) -> dict[str, Any]:
        try:
            r = httpx.get(f"{_data_base()}/api/v3/exchangeInfo", timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception:
            logger.exception("Vision exchangeInfo failed")
            return {"symbols": []}

    # Futures-only endpoints (not on Vision — use fapi.binance.com)
    def get_funding_rate(self, symbol: str) -> float:
        pair = normalize_pair(symbol)
        try:
            r = httpx.get(
                f"{_futures_base()}/fapi/v1/premiumIndex",
                params={"symbol": pair},
                timeout=10,
            )
            r.raise_for_status()
            return abs(float(r.json().get("lastFundingRate") or 0)) * 100
        except Exception:
            return 0.0

    def get_futures_exchange_info(self) -> dict[str, Any]:
        try:
            r = httpx.get(f"{_futures_base()}/fapi/v1/exchangeInfo", timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception:
            logger.exception("Futures exchangeInfo failed")
            return {"symbols": []}

    def get_futures_ticker_24hr(self, symbol: str | None = None) -> dict[str, dict] | dict:
        """Futures 24hr tickers — matches Binance USD-M Markets sort by 24h chg%."""
        try:
            params = {"symbol": normalize_pair(symbol)} if symbol else None
            r = httpx.get(f"{_futures_base()}/fapi/v1/ticker/24hr", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if symbol:
                return data
            return {t["symbol"]: t for t in data}
        except Exception:
            logger.exception("Futures 24hr ticker failed")
            return {} if not symbol else {}


binance_data = BinanceDataClient()
