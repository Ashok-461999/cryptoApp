"""Crypto futures signal scanner — quality SMC setups only (AMD, sweep, fib, structure)."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services.crypto_futures_client import futures_client
from app.services.crypto_watchlist import WatchlistSymbol, get_scan_symbol_order, get_top_24h_movers, get_watchlist, refresh_watchlist
from app.services.signal_tracker import enrich_live_signals, mark_user_taken, save_signal
from app.services.trade_analytics import get_disabled_setups
from app.signals.indicators import atr_pct
from app.signals.market_structure import swing_high_low
from app.signals.position_sizing_crypto import plan_crypto_futures
from app.signals.regime import detect_regime
from app.signals.schemas import T1_R, T2_R
from app.signals.setups import SETUP_FUNCTIONS
from app.signals.sl_levels import normalize_stop_loss
from app.signals.trade_decision import SETUP_PRIORITY, TOP_SETUPS, evaluate_trade_decision

logger = logging.getLogger(__name__)

STRUCTURE_TF = "5m"
ENTRY_TF = "1m"
LOOKBACK = 120

_CATEGORY_ORDER = {"mover": 0, "meme": 0, "major": 1, "alt": 2}
FOCUS_PAIRS = frozenset({"BTCUSDT", "PAXGUSDT"})


class CryptoScanner:
    def __init__(self) -> None:
        self._active_signals: list[dict] = []
        self._subscribers: list = []
        self._take_count_date: str = ""
        self._take_count_today: int = 0
        self._emitted_today: set[str] = set()
        self._skipped_today: set[str] = set()
        self._last_take_at: dict[str, datetime] = {}
        self._last_scan_total: int = 0
        self._trending_mover_pairs: set[str] = set()

    def subscribe(self, callback) -> None:
        self._subscribers.append(callback)

    def _utc_today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _in_cooldown(self, setup_name: str, symbol: str, direction: str) -> bool:
        settings = get_settings()
        key = f"{setup_name}:{symbol}:{direction.upper()}"
        last = self._last_take_at.get(key)
        if not last:
            return False
        gap = timedelta(minutes=max(5, settings.signal_cooldown_minutes))
        return datetime.now(timezone.utc) - last < gap

    def _sort_key(self, s: dict) -> tuple:
        settings = get_settings()
        setup_order = SETUP_PRIORITY.get(s.get("setup", ""), 9)
        mover_boost = 30 if s.get("pair") in self._trending_mover_pairs else 0
        vwap_vp_boost = 15 if s.get("setup") in ("anchored_vwap", "volume_profile", "order_flow", "liquidity_sweep") else 0
        meme_boost = 20 if settings.prioritize_meme_coins and s.get("category") in ("meme", "mover") else 0
        notify_boost = 40 if s.get("notify") else 0
        top_boost = 20 if s.get("strategy_tier") == "TOP" else 0
        major_boost = 10 if s.get("category") == "major" else 0
        cat_order = _CATEGORY_ORDER.get(s.get("category", "alt"), 2)
        return (
            setup_order,
            cat_order,
            -(s.get("confidence", 0) + meme_boost + mover_boost + vwap_vp_boost + notify_boost + top_boost + major_boost),
            -s.get("abs_change_pct_24h", 0),
            -s.get("risk_reward", 0),
            -s.get("volume_24h", 0),
        )

    def _refresh_take_count(self) -> None:
        from app.services.signal_tracker import count_open_signals_today

        today = self._utc_today()
        if today != self._take_count_date:
            self._take_count_date = today
            self._emitted_today = set()
            self._skipped_today = set()
        self._take_count_today = count_open_signals_today()

    def _prune_stale_active(self, max_minutes: int) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_minutes)
        kept: list[dict] = []
        for s in self._active_signals:
            ts = s.get("timestamp") or ""
            if not ts:
                kept.append(s)
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    kept.append(s)
            except ValueError:
                kept.append(s)
        self._active_signals = kept

    def get_active_signals(self) -> list[dict]:
        from app.services.binance_stream import price_stream
        from app.services.signal_tracker import load_live_signals_from_db

        if not self._active_signals:
            self._active_signals = load_live_signals_from_db()

        signals = [
            s for s in self._active_signals
            if self._signal_key(s) not in self._skipped_today
            and s.get("setup") != "fvg_retest"
        ]
        prices = {s.get("symbol", ""): price_stream.get_price(s.get("symbol", "")) or 0 for s in signals}
        return sorted(enrich_live_signals(signals, prices), key=self._sort_key)

    @staticmethod
    def _signal_key(sig: dict) -> str:
        return f"{sig.get('setup')}:{sig.get('symbol')}:{sig.get('direction')}"

    def scan_all(self) -> list[dict]:
        settings = get_settings()
        self._refresh_take_count()

        if not get_watchlist().symbols:
            refresh_watchlist()
        symbols = get_scan_symbol_order()
        movers = get_top_24h_movers()
        self._trending_mover_pairs = {s.pair for s in movers}
        self._last_scan_total = len(symbols)
        if movers:
            names = ", ".join(f"{s.base}({s.change_pct_24h:+.1f}%)" for s in movers[:8])
            logger.info("Scanning top 24h movers: %s … (%d total)", names, len(movers))
        candidates: list[dict] = []

        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = {pool.submit(self._scan_symbol, sym, settings): sym for sym in symbols}
            for fut in as_completed(futures):
                try:
                    candidates.extend(fut.result())
                except Exception:
                    sym = futures[fut]
                    logger.exception("Scan failed for %s", sym.pair)

        candidates.sort(key=self._sort_key)
        quality = [
            c for c in candidates
            if c.get("confidence", 0) >= settings.live_min_confidence
        ]

        cap = settings.max_take_signals_per_day
        if cap > 0:
            remaining = max(0, cap - self._take_count_today)
            per_scan = min(settings.max_signals_per_scan, remaining)
            take_signals = quality[:per_scan]
        else:
            take_signals = quality[: settings.max_signals_per_scan]

        if take_signals:
            by_key = {self._signal_key(s): s for s in self._active_signals}
            for sig in take_signals:
                by_key[self._signal_key(sig)] = sig
            self._active_signals = list(by_key.values())
        self._prune_stale_active(settings.scalp_holding_minutes)
        self._notify_scan_complete(self._active_signals)

        for sig in take_signals:
            key = self._signal_key(sig)
            sig["status"] = "LIVE"
            trade_id = save_signal(sig)
            if trade_id:
                sig["trade_id"] = trade_id
            if key not in self._emitted_today:
                self._emitted_today.add(key)
                self._take_count_today += 1
            self._last_take_at[key] = datetime.now(timezone.utc)
            for cb in self._subscribers:
                try:
                    cb(sig)
                except Exception:
                    logger.exception("Subscriber failed")

        return take_signals

    def force_scan(self) -> list[dict]:
        """Manual scan trigger — same as scheduled scan."""
        return self.scan_all()

    def take_signal(self, payload: dict) -> dict:
        """User chose to take a live signal — flag on existing reference track."""
        symbol = (payload.get("symbol") or "").upper()
        setup = payload.get("setup") or ""
        direction = (payload.get("direction") or "").upper()
        if not symbol or not setup or not direction:
            return {"ok": False, "error": "symbol, setup, and direction required"}

        trade_id = None
        for sig in self._active_signals:
            if (
                sig.get("symbol") == symbol
                and sig.get("setup") == setup
                and (sig.get("direction") or "").upper() == direction
            ):
                trade_id = sig.get("trade_id")
                break

        if not trade_id:
            trade_id = save_signal(payload)
        if not trade_id:
            return {"ok": False, "error": "Could not start tracking this signal"}

        mark_user_taken(trade_id)

        for sig in self._active_signals:
            if (
                sig.get("symbol") == symbol
                and sig.get("setup") == setup
                and (sig.get("direction") or "").upper() == direction
            ):
                sig["trade_id"] = trade_id
                sig["status"] = "TAKEN"
                sig["user_taken"] = True

        try:
            from app.services.price_sync import sync_tracked_symbols

            sync_tracked_symbols([symbol])
        except Exception:
            logger.exception("Price sync after take failed")

        for cb in self._subscribers:
            try:
                cb(payload)
            except Exception:
                logger.exception("Subscriber failed")

        return {"ok": True, "trade_id": trade_id, "status": "TAKEN"}

    def skip_signal(self, symbol: str, setup: str, direction: str = "") -> dict:
        """User skipped — hide from live list for today (reference PnL still tracked)."""
        sym = symbol.upper()
        dir_up = direction.upper()
        if dir_up:
            key = f"{setup}:{sym}:{dir_up}"
        else:
            key = None
        if key:
            self._skipped_today.add(key)
            self._active_signals = [s for s in self._active_signals if self._signal_key(s) != key]
        else:
            prefix = f"{setup}:{sym}:"
            self._skipped_today.update(
                self._signal_key(s) for s in self._active_signals if s.get("symbol") == sym and s.get("setup") == setup
            )
            self._active_signals = [
                s for s in self._active_signals
                if not (s.get("symbol") == sym and s.get("setup") == setup)
            ]
        return {"ok": True, "skipped": key or f"{setup}:{sym}"}

    def _notify_scan_complete(self, signals: list[dict]) -> None:
        try:
            from app.api.routes.signals_ws import broadcaster
            from app.services.price_sync import sync_tracked_symbols

            sync_tracked_symbols([s["symbol"] for s in signals if s.get("symbol")])
            if broadcaster._loop:
                asyncio.run_coroutine_threadsafe(broadcaster.broadcast_snapshot(), broadcaster._loop)
        except Exception:
            logger.exception("Post-scan notify failed")

    @staticmethod
    def _confirm_entry_1m(direction: str, entry_candles: list[dict]) -> bool:
        """1m trigger must confirm direction with body + micro structure break."""
        if len(entry_candles) < 4:
            return False
        df = futures_client.candles_to_df(entry_candles)
        bar = df.iloc[-1]
        prev = df.iloc[-2]
        body = float(bar["close"]) - float(bar["open"])
        full_range = float(bar["high"]) - float(bar["low"])
        if full_range <= 0:
            return False
        body_pct = abs(body) / full_range
        if body_pct < 0.38:
            return False
        vol = float(bar["volume"])
        avg_vol = float(df["volume"].tail(20).mean()) if len(df) >= 20 else vol
        if vol < avg_vol * 1.05:
            return False
        if direction == "bullish":
            return body > 0 and float(bar["close"]) > float(prev["high"])
        return body < 0 and float(bar["close"]) < float(prev["low"])

    def _scan_symbol(self, sym: WatchlistSymbol, settings) -> list[dict]:
        struct_candles = futures_client.get_futures_candles(sym.pair, STRUCTURE_TF, LOOKBACK)
        entry_candles = futures_client.get_futures_candles(sym.pair, ENTRY_TF, 60)
        if len(struct_candles) < 60:
            return []

        df = futures_client.candles_to_df(struct_candles)
        regime = detect_regime(df)
        atr_p = atr_pct(df)
        swing_high, swing_low = swing_high_low(df)
        bar_5m = df.iloc[-1]
        disabled_setups = get_disabled_setups()
        funding = futures_client.get_funding_rate(sym.pair)
        if funding > settings.max_funding_rate_pct:
            return []
        if sym.spread_pct > settings.max_spread_pct:
            return []

        results: list[dict] = []
        for setup_name, fn in SETUP_FUNCTIONS.items():
            if setup_name in disabled_setups:
                continue
            result = fn(df)
            if not result.fired or not result.stop_loss:
                continue

            direction = "LONG" if result.direction == "bullish" else "SHORT"
            if self._in_cooldown(setup_name, sym.pair, direction):
                continue

            decision = evaluate_trade_decision(setup_name, result, regime, sym.category)
            if not decision["can_take"]:
                continue

            if not self._confirm_entry_1m(result.direction or "bullish", entry_candles):
                continue

            entry_df = futures_client.candles_to_df(entry_candles)
            entry = float(entry_df.iloc[-1]["close"])
            atr_val = entry * atr_p / 100.0 if atr_p > 0 else entry * 0.008
            stop = normalize_stop_loss(
                entry=entry,
                direction=result.direction or "bullish",
                proposed_stop=float(result.stop_loss),
                bar_low=float(bar_5m["low"]),
                bar_high=float(bar_5m["high"]),
                swing_low=swing_low,
                swing_high=swing_high,
                atr=atr_val,
                tier=sym.tier,
            )
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            sign = 1 if direction == "LONG" else -1
            t1 = entry + sign * risk * T1_R
            t2 = entry + sign * risk * T2_R

            plan = plan_crypto_futures(
                symbol=sym.pair,
                direction=direction,
                entry=entry,
                stop_loss=stop,
                target_1=t1,
                target_2=t2,
                capital_usdt=settings.crypto_capital_usdt,
                risk_percent=settings.risk_percent,
                max_deploy_pct=settings.max_deploy_pct,
                atr_pct=atr_p,
                sl_basis=result.sl_basis,
            )
            if not plan.can_afford:
                continue

            confidence = decision["take_confidence"]
            min_conf = settings.mover_min_confidence if sym.category in ("meme", "mover") else settings.scalp_min_confidence
            if confidence < min_conf:
                continue
            notify = confidence >= settings.notify_min_confidence

            signal = plan.to_dict()
            signal.update({
                "setup": setup_name,
                "confidence": confidence,
                "notify": notify,
                "signal_grade": "A+" if notify else "A",
                "strategy_tier": decision.get("strategy_tier", "TOP" if setup_name in TOP_SETUPS else "STD"),
                "decision_reason": decision["decision_reason"],
                "regime": regime.regime.value,
                "regime_summary": regime.summary,
                "trend_direction": regime.trend_direction,
                "sl_basis": result.sl_basis,
                "chart_timeframe": STRUCTURE_TF,
                "entry_timeframe": ENTRY_TF,
                "validity_points": [
                    f"Strategy: {setup_name.replace('_', ' ').title()} — {result.reason}",
                    f"Structure TF: {STRUCTURE_TF} · Entry trigger: {ENTRY_TF} confirmed",
                    f"Market structure: {regime.summary} · trend {regime.trend_direction}",
                    f"Trade decision: {decision['decision_reason']}",
                    f"Risk:Reward {round(plan.risk_reward, 2)} to T1 (min {settings.min_rr_for_take})",
                    f"Confidence: {confidence}% — {'A+ NOTIFY' if notify else 'A quality scalp'}",
                    f"SL basis: {result.sl_basis}",
                    f"Leverage: {plan.leverage}x · Risk ₹{settings.risk_per_trade_inr:.0f} · Scalp target ₹{settings.scalp_target_inr:.0f}+ (1:2)",
                    f"24h move: {sym.change_pct_24h:+.1f}% · Funding: {round(funding, 4)}% · {sym.category.upper()}",
                ],
                "volume_24h": sym.volume_24h_usdt,
                "change_pct_24h": sym.change_pct_24h,
                "abs_change_pct_24h": sym.abs_change_pct_24h,
                "category": sym.category,
                "tier": sym.tier,
                "status": "LIVE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "funding_rate_pct": round(funding, 4),
                "max_loss_inr": round(plan.max_loss_usdt * settings.usdt_to_inr, 0),
                "target_pnl_inr": round(plan.target_profit_usdt * settings.usdt_to_inr, 0),
                "target_profit_inr": round(plan.target_profit_usdt * settings.usdt_to_inr, 0),
                "margin_inr": round(plan.margin_usdt * settings.usdt_to_inr, 0),
                "notional_inr": round(plan.notional_usdt * settings.usdt_to_inr, 0),
                "position_inr": round(plan.margin_usdt * settings.usdt_to_inr * plan.leverage, 0),
                "capital_inr": settings.crypto_capital_inr,
                "risk_per_trade_inr": settings.risk_per_trade_inr,
                "spread_warning": sym.spread_pct > 0.1,
                "trading_style": settings.trading_style,
            })
            results.append(signal)

        if not results:
            return []

        by_dir: dict[str, list[dict]] = {"LONG": [], "SHORT": []}
        for r in results:
            d = (r.get("direction") or "LONG").upper()
            by_dir.setdefault(d, []).append(r)

        allow_both = sym.pair in FOCUS_PAIRS
        picked: list[dict] = []

        def _best(items: list[dict]) -> dict | None:
            if not items:
                return None
            items.sort(key=lambda s: (
                SETUP_PRIORITY.get(s.get("setup", ""), 9),
                -s.get("confidence", 0),
                -s.get("risk_reward", 0),
            ))
            return items[0]

        if allow_both:
            for d in ("LONG", "SHORT"):
                best = _best(by_dir.get(d, []))
                if best:
                    picked.append(best)
        else:
            all_best = _best(results)
            if all_best:
                picked.append(all_best)

        return picked


crypto_scanner = CryptoScanner()
