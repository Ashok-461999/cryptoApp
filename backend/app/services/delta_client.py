"""Delta Exchange India REST client — HMAC auth for private endpoints."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class DeltaClient:
    def __init__(self) -> None:
        s = get_settings()
        self._base = s.delta_exchange_base_url.rstrip("/")
        self._key = s.delta_api_key
        self._secret = s.delta_api_secret

    def is_configured(self) -> bool:
        return bool(self._key and self._secret)

    def _sign(self, method: str, path: str, query: dict | None = None, body: str = "") -> dict[str, str]:
        ts = str(int(time.time()))
        q = f"?{urlencode(query)}" if query else ""
        payload = method.upper() + ts + path + q + body
        sig = hmac.new(self._secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return {
            "api-key": self._key,
            "timestamp": ts,
            "signature": sig,
            "User-Agent": "scalptrack-delta/1.0",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, *, params: dict | None = None, json_body: Any = None) -> dict | list:
        if not self.is_configured():
            return {}
        body = ""
        if json_body is not None:
            import json
            body = json.dumps(json_body, separators=(",", ":"))
        headers = self._sign(method, path, params, body)
        url = f"{self._base}{path}"
        try:
            r = httpx.request(method, url, params=params, content=body or None, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            return data.get("result", data) if isinstance(data, dict) else data
        except Exception:
            logger.debug("Delta private %s %s failed", method, path)
            return {}

    def get_fills(self, limit: int = 50) -> list[dict]:
        rows = self._request("GET", "/v2/fills", params={"page_size": limit})
        return rows if isinstance(rows, list) else []

    def get_wallet_balances(self) -> list[dict]:
        rows = self._request("GET", "/v2/wallet/balances")
        return rows if isinstance(rows, list) else []


delta_client = DeltaClient()
