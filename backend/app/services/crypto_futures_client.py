"""Market data facade — routes candles/prices through Binance Vision."""

from __future__ import annotations

import pandas as pd

from app.services.binance_data import binance_data


class CryptoFuturesClient:
    def get_futures_candles(
        self, symbol: str, interval: str = "5m", limit: int = 120,
    ) -> list[dict]:
        return binance_data.get_klines(symbol, interval, limit)

    def candles_to_df(self, candles: list[dict]) -> pd.DataFrame:
        if not candles:
            return pd.DataFrame()
        return pd.DataFrame(candles)

    def get_funding_rate(self, symbol: str) -> float:
        return binance_data.get_funding_rate(symbol)

    def get_signed_funding_rate(self, symbol: str) -> float:
        return binance_data.get_signed_funding_rate(symbol)

    def get_price(self, symbol: str) -> float:
        return binance_data.get_price(symbol)


futures_client = CryptoFuturesClient()
