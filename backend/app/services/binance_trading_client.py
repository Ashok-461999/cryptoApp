"""Signed Binance USD-M Futures REST client — place real orders."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.services.binance_data import binance_data, normalize_pair

logger = logging.getLogger(__name__)

_symbol_rules: dict[str, dict[str, float]] = {}
_max_leverage_cache: dict[str, int] = {}


class BinanceTradingError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class BinanceTradingClient:
    def __init__(self) -> None:
        self._client = httpx.Client(timeout=20.0)
        self._hedge_mode: bool | None = None

    def is_configured(self) -> bool:
        s = get_settings()
        return bool(s.binance_api_key and s.binance_api_secret)

    def _base_url(self) -> str:
        s = get_settings()
        if s.binance_futures_testnet:
            return "https://testnet.binancefuture.com"
        return s.binance_futures_base_url.rstrip("/")

    def _sign(self, params: dict[str, Any]) -> dict[str, Any]:
        s = get_settings()
        params = dict(params)
        params["timestamp"] = int(time.time() * 1000)
        query = urlencode(params, doseq=True)
        sig = hmac.new(
            s.binance_api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = sig
        return params

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": get_settings().binance_api_key}

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.is_configured():
            raise BinanceTradingError("Binance API keys not configured")
        params = self._sign(params or {})
        url = f"{self._base_url()}{path}"
        if method == "GET":
            r = self._client.get(url, params=params, headers=self._headers())
        elif method == "POST":
            r = self._client.post(url, params=params, headers=self._headers())
        elif method == "DELETE":
            r = self._client.delete(url, params=params, headers=self._headers())
        else:
            raise ValueError(f"Unsupported method {method}")
        if r.status_code >= 400:
            try:
                err = r.json()
                code = err.get("code")
                msg = err.get("msg", r.text)
            except Exception:
                code = None
                msg = r.text
            raise BinanceTradingError(f"Binance {path} failed: {msg}", code=code)
        return r.json()

    def ping(self) -> bool:
        try:
            self._request("GET", "/fapi/v2/account")
            return True
        except Exception as exc:
            logger.warning("Binance account ping failed: %s", exc)
            return False

    def get_usdt_balance(self) -> float:
        data = self._request("GET", "/fapi/v2/balance")
        for row in data:
            if row.get("asset") == "USDT":
                return float(row.get("availableBalance") or 0)
        return 0.0

    def get_today_realized_pnl_usdt(self) -> float:
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            rows = self._request(
                "GET",
                "/fapi/v1/income",
                {
                    "incomeType": "REALIZED_PNL",
                    "startTime": int(start.timestamp() * 1000),
                    "limit": 1000,
                },
            )
            return sum(float(r.get("income") or 0) for r in rows)
        except Exception:
            logger.exception("Failed to fetch Binance today PnL")
            return 0.0

    def get_wallet_summary(self) -> dict[str, float]:
        """Live Binance Futures wallet — balance, unrealized & today realized PnL."""
        s = get_settings()
        acc = self._request("GET", "/fapi/v2/account")
        wallet = float(acc.get("totalWalletBalance") or 0)
        unrealized = float(acc.get("totalUnrealizedProfit") or 0)
        available = float(acc.get("availableBalance") or 0)
        equity = float(acc.get("totalMarginBalance") or wallet)
        today_pnl = self.get_today_realized_pnl_usdt()
        rate = s.usdt_to_inr
        return {
            "wallet_usdt": round(wallet, 2),
            "available_usdt": round(available, 2),
            "unrealized_pnl_usdt": round(unrealized, 2),
            "equity_usdt": round(equity, 2),
            "today_realized_pnl_usdt": round(today_pnl, 2),
            "wallet_inr": round(wallet * rate, 0),
            "available_inr": round(available * rate, 0),
            "unrealized_pnl_inr": round(unrealized * rate, 0),
            "equity_inr": round(equity * rate, 0),
            "today_pnl_inr": round(today_pnl * rate, 0),
        }

    def is_hedge_mode(self) -> bool:
        if self._hedge_mode is not None:
            return self._hedge_mode
        try:
            data = self._request("GET", "/fapi/v1/positionSide/dual")
            self._hedge_mode = bool(data.get("dualSidePosition"))
        except Exception as exc:
            logger.warning("positionSide/dual check failed: %s", exc)
            self._hedge_mode = False
        return self._hedge_mode

    def ensure_one_way_mode(self) -> bool:
        """Prefer one-way mode so orders work without positionSide."""
        if not self.is_hedge_mode():
            return True
        try:
            self._request("POST", "/fapi/v1/positionSide/dual", {"dualSidePosition": "false"})
            self._hedge_mode = False
            logger.info("Binance account set to one-way position mode")
            return True
        except BinanceTradingError as exc:
            logger.warning("Cannot switch to one-way mode (close positions first?): %s", exc)
            return False

    def _order_params(self, base: dict[str, Any], position_side: str | None = None) -> dict[str, Any]:
        params = dict(base)
        if self.is_hedge_mode():
            if not position_side:
                raise BinanceTradingError("Hedge mode requires positionSide — close open positions or switch to one-way mode")
            params["positionSide"] = position_side.upper()
        return params

    def get_position_amt(self, symbol: str) -> float:
        pair = normalize_pair(symbol)
        rows = self._request("GET", "/fapi/v2/positionRisk", {"symbol": pair})
        for row in rows:
            if row.get("symbol") == pair:
                return float(row.get("positionAmt") or 0)
        return 0.0

    def _load_symbol_rules(self, symbol: str) -> dict[str, float]:
        pair = normalize_pair(symbol)
        if pair in _symbol_rules:
            return _symbol_rules[pair]
        info = binance_data.get_futures_exchange_info()
        for sym in info.get("symbols", []):
            if sym.get("symbol") != pair:
                continue
            rules = {"step_size": 0.001, "tick_size": 0.01, "min_qty": 0.001, "min_notional": 5.0}
            for f in sym.get("filters", []):
                if f.get("filterType") == "LOT_SIZE":
                    rules["step_size"] = float(f.get("stepSize") or rules["step_size"])
                    rules["min_qty"] = float(f.get("minQty") or rules["min_qty"])
                elif f.get("filterType") == "PRICE_FILTER":
                    rules["tick_size"] = float(f.get("tickSize") or rules["tick_size"])
                elif f.get("filterType") == "MIN_NOTIONAL":
                    rules["min_notional"] = float(f.get("notional") or rules["min_notional"])
            _symbol_rules[pair] = rules
            return rules
        return {"step_size": 0.001, "tick_size": 0.01, "min_qty": 0.001, "min_notional": 5.0}

    @staticmethod
    def _round_step(value: float, step: float) -> float:
        if step <= 0:
            return value
        d = Decimal(str(value))
        s = Decimal(str(step))
        return float((d / s).to_integral_value(rounding=ROUND_DOWN) * s)

    def round_qty(self, symbol: str, qty: float) -> float:
        rules = self._load_symbol_rules(symbol)
        return max(self._round_step(qty, rules["step_size"]), rules["min_qty"])

    def round_price(self, symbol: str, price: float) -> float:
        rules = self._load_symbol_rules(symbol)
        return self._round_step(price, rules["tick_size"])

    def get_max_leverage(self, symbol: str) -> int:
        """Binance per-symbol max leverage from leverage brackets."""
        pair = normalize_pair(symbol)
        if pair in _max_leverage_cache:
            return _max_leverage_cache[pair]
        try:
            rows = self._request("GET", "/fapi/v1/leverageBracket", {"symbol": pair})
            for row in rows:
                if row.get("symbol") != pair:
                    continue
                brackets = row.get("brackets") or []
                mx = max(int(b.get("initialLeverage") or 1) for b in brackets) if brackets else 20
                _max_leverage_cache[pair] = mx
                return mx
        except Exception as exc:
            logger.warning("leverageBracket %s failed: %s", pair, exc)
        return 20

    def set_leverage(self, symbol: str, leverage: int) -> int:
        pair = normalize_pair(symbol)
        cap = self.get_max_leverage(pair)
        lev = max(1, min(int(leverage), cap))
        last_err: BinanceTradingError | None = None
        for try_lev in range(lev, 0, -5):
            try:
                self._request("POST", "/fapi/v1/leverage", {"symbol": pair, "leverage": try_lev})
                if try_lev != leverage:
                    logger.info("Leverage capped %s: requested %sx -> %sx (max %sx)", pair, leverage, try_lev, cap)
                return try_lev
            except BinanceTradingError as exc:
                if exc.code in (-4046,):
                    return try_lev
                last_err = exc
                if "not valid" in str(exc).lower():
                    continue
                raise
        if last_err:
            raise last_err
        return 1

    def set_isolated_margin(self, symbol: str) -> None:
        pair = normalize_pair(symbol)
        try:
            self._request("POST", "/fapi/v1/marginType", {"symbol": pair, "marginType": "ISOLATED"})
        except BinanceTradingError as exc:
            if exc.code not in (-4046,):
                raise

    def place_market_order(
        self, symbol: str, side: str, quantity: float, *, position_side: str | None = None
    ) -> dict[str, Any]:
        pair = normalize_pair(symbol)
        qty = self.round_qty(pair, quantity)
        rules = self._load_symbol_rules(pair)
        if qty < rules["min_qty"]:
            raise BinanceTradingError(f"Quantity {qty} below min {rules['min_qty']}")
        return self._request(
            "POST",
            "/fapi/v1/order",
            self._order_params(
                {
                    "symbol": pair,
                    "side": side.upper(),
                    "type": "MARKET",
                    "quantity": qty,
                    "newOrderRespType": "RESULT",
                },
                position_side,
            ),
        )

    def place_stop_market(
        self, symbol: str, side: str, stop_price: float, quantity: float, *, position_side: str | None = None
    ) -> dict[str, Any]:
        return self._place_algo_conditional(
            symbol, side, "STOP_MARKET", stop_price, quantity, position_side=position_side
        )

    def place_take_profit_market(
        self, symbol: str, side: str, stop_price: float, quantity: float, *, position_side: str | None = None
    ) -> dict[str, Any]:
        return self._place_algo_conditional(
            symbol, side, "TAKE_PROFIT_MARKET", stop_price, quantity, position_side=position_side
        )

    def _place_algo_conditional(
        self,
        symbol: str,
        side: str,
        order_type: str,
        trigger_price: float,
        quantity: float,
        *,
        position_side: str | None = None,
    ) -> dict[str, Any]:
        """Binance migrated STOP/TP orders to algo service (Dec 2025)."""
        pair = normalize_pair(symbol)
        return self._request(
            "POST",
            "/fapi/v1/algoOrder",
            self._order_params(
                {
                    "algoType": "CONDITIONAL",
                    "symbol": pair,
                    "side": side.upper(),
                    "type": order_type.upper(),
                    "triggerPrice": self.round_price(pair, trigger_price),
                    "quantity": self.round_qty(pair, quantity),
                    "reduceOnly": "true",
                    "workingType": "MARK_PRICE",
                },
                position_side,
            ),
        )

    def cancel_all_orders(self, symbol: str) -> None:
        pair = normalize_pair(symbol)
        try:
            self._request("DELETE", "/fapi/v1/allOpenOrders", {"symbol": pair})
        except BinanceTradingError as exc:
            logger.warning("Cancel orders %s: %s", pair, exc)
        try:
            self._request("DELETE", "/fapi/v1/algoOpenOrders", {"symbol": pair})
        except BinanceTradingError as exc:
            logger.warning("Cancel algo orders %s: %s", pair, exc)

    def close_position_market(self, symbol: str) -> dict[str, Any] | None:
        pair = normalize_pair(symbol)
        rows = self._request("GET", "/fapi/v2/positionRisk", {"symbol": pair})
        for row in rows:
            if row.get("symbol") != pair:
                continue
            amt = float(row.get("positionAmt") or 0)
            if abs(amt) < 1e-12:
                continue
            side = "SELL" if amt > 0 else "BUY"
            pos_side = row.get("positionSide") if self.is_hedge_mode() else None
            qty = self.round_qty(pair, abs(amt))
            return self.place_market_order(pair, side, qty, position_side=pos_side)
        return None


binance_trading = BinanceTradingClient()
