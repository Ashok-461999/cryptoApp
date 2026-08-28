"""Global market news — crypto + macro feeds with affected-market tags."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_BULLISH = frozenset({
    "surge", "rally", "bullish", "gain", "gains", "rise", "rises", "rising", "up",
    "breakout", "record", "high", "approval", "approved", "adoption", "inflow",
    "buy", "accumulate", "recovery", "rebound", "soar", "jump", "etf", "partnership",
    "upgrade", "optimism", "growth", "positive", "outperform", "rate cut", "easing",
})
_BEARISH = frozenset({
    "crash", "bearish", "drop", "drops", "fall", "falls", "falling", "down", "decline",
    "loss", "losses", "ban", "banned", "hack", "hacked", "exploit", "liquidation",
    "fear", "selloff", "sell", "dump", "warning", "risk", "lawsuit", "sec", "probe",
    "outflow", "negative", "underperform", "plunge", "sink", "collapse", "rate hike",
    "recession", "war", "sanction", "default",
})

# (keywords, market tag, impact hint)
_MARKET_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("bitcoin", "btc", "crypto etf", "microstrategy", "satoshi"), "BTC", "BTC futures — watch 5m structure"),
    (("gold", "paxg", "precious metal", "bullion", "xau"), "GOLD", "Gold PAXG — safe-haven flows"),
    (("ethereum", " ether", "eth ", "defi", "layer 2", "l2 "), "ETH", "ETH & DeFi alts"),
    (("meme", "doge", "shib", "pepe", "bonk", "wif", "floki"), "MEME", "Meme coins — high volatility"),
    (("solana", " sol ", "bnb", "altcoin", "alt season"), "ALTS", "Altcoin basket"),
    (("fed", "fomc", "cpi", "inflation", "interest rate", "powell", "treasury", "jobs report"), "MACRO", "Macro — moves BTC, GOLD, risk assets"),
    (("war", "geopolit", "sanction", "missile", "conflict", "tariff", "trade war"), "GLOBAL", "Geopolitical risk — BTC & GOLD"),
    (("oil", "crude", "opec", "energy"), "COMMODITIES", "Commodities — inflation & risk sentiment"),
    (("nasdaq", "s&p", "dow", "stock market", "wall street", "equities"), "STOCKS", "Equities correlation with BTC"),
    (("dollar", "dxy", "usd", "yen", "euro", "forex"), "FX", "FX moves — inverse to BTC often"),
    (("regulation", "sec ", "cftc", "ban crypto", "lawsuit"), "REGULATION", "Regulatory headline risk for crypto"),
]

_RSS_FEEDS = (
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("Guardian Business", "https://www.theguardian.com/business/rss"),
)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def score_sentiment(title: str, body: str = "") -> dict:
    words = _tokenize(f"{title} {body}")
    bull = len(words & _BULLISH)
    bear = len(words & _BEARISH)
    total = bull + bear
    if total == 0:
        return {"sentiment": "neutral", "score": 0, "bull_score": bull, "bear_score": bear}
    score = round((bull - bear) / max(total, 1) * 100)
    if score >= 25:
        label = "bullish"
    elif score <= -25:
        label = "bearish"
    else:
        label = "neutral"
    return {"sentiment": label, "score": score, "bull_score": bull, "bear_score": bear}


def detect_market_impact(title: str, body: str = "", categories: str = "") -> dict:
    text = f"{title} {body} {categories}".lower()
    affected: list[str] = []
    hints: list[str] = []
    for keywords, market, hint in _MARKET_RULES:
        if any(k in text for k in keywords):
            if market not in affected:
                affected.append(market)
                hints.append(hint)
    if not affected:
        affected = ["CRYPTO"]
        hints = ["General crypto sentiment — check BTC chart first"]
    return {
        "affected_markets": affected,
        "market_impact": " · ".join(hints[:3]),
        "primary_market": affected[0],
    }


def _article_reaction(sentiment: str, impact: dict) -> str:
    markets = ", ".join(impact.get("affected_markets", [])[:4])
    if sentiment == "bullish":
        return f"Bullish tilt — {markets} may see risk-on reaction. Wait for chart entry."
    if sentiment == "bearish":
        return f"Bearish tilt — {markets} headline risk. Avoid chasing; use strict SL."
    return f"Neutral — monitor {markets}. Trade setups only, not news alone."


def _parse_rss(xml_text: str, source: str, limit: int) -> list[dict]:
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for node in root.findall(".//item")[:limit]:
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        desc = re.sub(r"<[^>]+>", " ", node.findtext("description") or "")[:600]
        link = node.findtext("link") or ""
        pub = node.findtext("pubDate") or node.findtext("{http://www.w3.org/2005/Atom}published") or ""
        published_at = datetime.now(timezone.utc).isoformat()
        if pub:
            try:
                from email.utils import parsedate_to_datetime

                published_at = parsedate_to_datetime(pub).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
        sent = score_sentiment(title, desc)
        impact = detect_market_impact(title, desc, categories=source)
        items.append({
            "id": f"rss-{hash(title) & 0xFFFFFFFF}",
            "title": title,
            "source": source,
            "url": link,
            "published_at": published_at,
            "categories": source,
            "sentiment": sent["sentiment"],
            "sentiment_score": sent["score"],
            "affected_markets": impact["affected_markets"],
            "primary_market": impact["primary_market"],
            "market_impact": impact["market_impact"],
            "reaction": _article_reaction(sent["sentiment"], impact),
            "feed_type": "global",
        })
    return items


def _fetch_rss_feeds(per_feed: int = 12) -> list[dict]:
    merged: list[dict] = []
    headers = {"User-Agent": "ScalpTrack/1.0 (market-news)"}
    for name, url in _RSS_FEEDS:
        try:
            r = httpx.get(url, timeout=12, follow_redirects=True, headers=headers)
            if r.status_code != 200:
                continue
            merged.extend(_parse_rss(r.text, name, per_feed))
        except Exception:
            logger.debug("RSS skip %s", name)
    return merged


def _fetch_cryptocompare(limit: int) -> list[dict]:
    items: list[dict] = []
    r = httpx.get(
        "https://min-api.cryptocompare.com/data/v2/news/",
        params={"lang": "EN"},
        timeout=15,
    )
    r.raise_for_status()
    for art in (r.json().get("Data") or [])[:limit]:
        title = art.get("title") or ""
        body = (art.get("body") or "")[:600]
        cats = art.get("categories", "") or ""
        sent = score_sentiment(title, body)
        impact = detect_market_impact(title, body, cats)
        items.append({
            "id": str(art.get("id", "")),
            "title": title,
            "source": art.get("source_info", {}).get("name") or art.get("source", "CryptoCompare"),
            "url": art.get("url") or art.get("guid", ""),
            "published_at": datetime.fromtimestamp(
                int(art.get("published_on") or 0), tz=timezone.utc
            ).isoformat(),
            "categories": cats,
            "sentiment": sent["sentiment"],
            "sentiment_score": sent["score"],
            "affected_markets": impact["affected_markets"],
            "primary_market": impact["primary_market"],
            "market_impact": impact["market_impact"],
            "reaction": _article_reaction(sent["sentiment"], impact),
            "feed_type": "crypto",
        })
    return items


def _dedupe(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        key = re.sub(r"[^a-z0-9]", "", (it.get("title") or "").lower())[:80]
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _market_reaction(summary: dict) -> str:
    bull = summary.get("bullish_count", 0)
    bear = summary.get("bearish_count", 0)
    top = summary.get("top_affected_markets") or []
    top_txt = ", ".join(top[:5]) if top else "BTC, GOLD"
    if bull > bear * 1.5 and bull >= 3:
        return f"Live flow BULLISH — {top_txt} may see risk-on. Favor long setups on pullbacks."
    if bear > bull * 1.5 and bear >= 3:
        return f"Live flow BEARISH — {top_txt} under pressure. Caution on longs; shorts need SL."
    if bull > bear:
        return f"Slightly bullish — watch {top_txt} for continuation if volume confirms."
    if bear > bull:
        return f"Slightly bearish — {top_txt} may dip on headlines; wait for structure."
    return f"Mixed global news — {top_txt} mixed. Trade A+ chart setups only."


def fetch_market_news(limit: int = 40) -> dict:
    items: list[dict] = []
    try:
        items.extend(_fetch_cryptocompare(min(limit, 35)))
    except Exception:
        logger.debug("CryptoCompare news unavailable (optional feed)")
    try:
        items.extend(_fetch_rss_feeds(per_feed=10))
    except Exception:
        logger.exception("RSS news failed")

    items = _dedupe(items)
    items.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    items = items[:limit]

    bullish = sum(1 for i in items if i["sentiment"] == "bullish")
    bearish = sum(1 for i in items if i["sentiment"] == "bearish")
    neutral = len(items) - bullish - bearish
    avg_score = round(sum(i["sentiment_score"] for i in items) / len(items)) if items else 0

    market_counts: dict[str, int] = {}
    for it in items:
        for m in it.get("affected_markets") or []:
            market_counts[m] = market_counts.get(m, 0) + 1
    top_markets = sorted(market_counts.keys(), key=lambda k: market_counts[k], reverse=True)

    if avg_score >= 20:
        mood = "bullish"
    elif avg_score <= -20:
        mood = "bearish"
    else:
        mood = "neutral"

    summary = {
        "bullish_count": bullish,
        "bearish_count": bearish,
        "neutral_count": neutral,
        "market_mood": mood,
        "avg_sentiment_score": avg_score,
        "top_affected_markets": top_markets,
        "total_headlines": len(items),
        "is_live": True,
    }
    summary["market_reaction"] = _market_reaction(summary)

    return {
        "items": items,
        "summary": summary,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sources": ["CoinDesk", "Cointelegraph", "BBC Business", "Reuters", "Yahoo Finance", "CNBC", "Guardian"],
    }
