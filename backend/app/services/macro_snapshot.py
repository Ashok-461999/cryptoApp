"""Macro snapshot — Fear & Greed, BTC dominance, total market cap."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_CACHE: dict = {}
_CACHE_AT: datetime | None = None
_TTL_SEC = 300


def get_macro_snapshot() -> dict:
    global _CACHE_AT
    now = datetime.now(timezone.utc)
    if _CACHE_AT and (now - _CACHE_AT).total_seconds() < _TTL_SEC and _CACHE:
        return dict(_CACHE)

    out = {
        "btc_dominance_pct": 0.0,
        "total_market_cap_usd": 0.0,
        "fear_greed_index": 50,
        "fear_greed_label": "Neutral",
        "dxy_note": "Watch USD strength — inverse to BTC often",
        "generated_at": now.isoformat(),
    }

    try:
        r = httpx.get("https://api.coingecko.com/api/v3/global", timeout=12)
        r.raise_for_status()
        g = r.json().get("data") or {}
        out["btc_dominance_pct"] = round(float(g.get("market_cap_percentage", {}).get("btc", 0)), 2)
        out["total_market_cap_usd"] = round(float(g.get("total_market_cap", {}).get("usd", 0)) / 1e12, 3)
    except Exception:
        logger.debug("CoinGecko global failed")

    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        r.raise_for_status()
        row = (r.json().get("data") or [{}])[0]
        out["fear_greed_index"] = int(row.get("value") or 50)
        out["fear_greed_label"] = row.get("value_classification") or "Neutral"
    except Exception:
        logger.debug("Fear & Greed API failed")

    _CACHE.clear()
    _CACHE.update(out)
    _CACHE_AT = now
    return dict(out)
