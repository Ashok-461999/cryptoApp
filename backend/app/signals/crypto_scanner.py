"""Crypto futures signal scanner — 1m buy-dip / sell-top on fast movers."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.services.binance_account import (
    fixed_risk_usdt,
    get_available_usdt,
    get_live_capital_usdt,
    max_leverage_for_capital,
    min_leverage_for_capital,
    per_trade_deploy_pct,
    scalp_rr_for_confidence,
)
from app.services.crypto_futures_client import futures_client
from app.services.crypto_watchlist import WatchlistSymbol, get_scan_symbol_order, get_top_24h_movers, get_watchlist, refresh_watchlist
from app.services.signal_tracker import enrich_live_signals, mark_user_taken, save_signal
from app.services.trade_analytics import get_disabled_setups
from app.services.trading_fees import estimated_entry_drag_usdt, round_trip_fee_usdt, tp_price_from_rr
from app.signals.indicators import atr_pct
from app.signals.market_structure import swing_high_low
from app.signals.momentum_scalp import SETUP_NAME as DIP_TOP_SETUP, dip_top_scalp
from app.signals.position_sizing_crypto import plan_crypto_futures
from app.signals.regime import detect_regime
from app.signals.setups import SETUP_FUNCTIONS
from app.signals.sl_levels import normalize_stop_loss
from app.signals.trade_decision import PERMANENTLY_DISABLED_SETUPS, SETUP_PRIORITY, TOP_SETUPS, evaluate_trade_decision

logger = logging.getLogger(__name__)

STRUCTURE_TF = "5m"
ENTRY_TF = "1m"
LOOKBACK = 120

_CATEGORY_ORDER = {"mover": 0, "meme": 0, "major": 1, "alt": 2}
FOCUS_PAIRS = frozenset({"BTCUSDT", "PAXGUSDT"})
SCALP_SETUPS = frozenset({DIP_TOP_SETUP, "momentum_scalp", "dip_top_scalp"})


class CryptoScanner:
    def __init__(self) -> None:
        self._active_signals: list[dict] = []
        self._subscribers: list = []
        self._take_count_date: str = ""
        self._take_count_today: int = 0
        self._emitted_today: set[str] = set()
        self._skipped_today: set[str] = set()
        self._high_priority_emitted_today: int = 0
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
        gap = timedelta(minutes=max(1, settings.signal_cooldown_minutes))
        return datetime.now(timezone.utc) - last < gap

    def _sort_key(self, s: dict) -> tuple:
        settings = get_settings()
        high_first = 0 if s.get("priority_tier") == "HIGH" else 1
        setup_order = SETUP_PRIORITY.get(s.get("setup", ""), 9)
        mover_boost = 30 if s.get("pair") in self._trending_mover_pairs else 0
        vwap_vp_boost = 15 if s.get("setup") in SCALP_SETUPS else 0
        meme_boost = 20 if settings.prioritize_meme_coins and s.get("category") in ("meme", "mover") else 0
        notify_boost = 40 if s.get("notify") else 0
        top_boost = 20 if s.get("strategy_tier") == "TOP" else 0
        major_boost = 10 if s.get("category") == "major" else 0
        cat_order = _CATEGORY_ORDER.get(s.get("category", "alt"), 2)
        return (
            high_first,
            setup_order,
            cat_order,
            -(s.get("confidence", 0) + meme_boost + mover_boost + vwap_vp_boost + notify_boost + top_boost + major_boost),
            -s.get("abs_change_pct_24h", 0),
            -s.get("risk_reward", 0),
            -s.get("volume_24h", 0),
        )

    def _refresh_take_count(self) -> None:
        today = self._utc_today()
        if today != self._take_count_date:
            self._take_count_date = today
            self._emitted_today = set()
            self._skipped_today = set()
            self._high_priority_emitted_today = 0
            self._take_count_today = 0

    def _qualifies_high_priority(self, signal: dict, settings) -> bool:
        return (
            signal.get("confidence", 0) >= settings.high_priority_min_confidence
            and signal.get("risk_reward", 0) >= settings.high_priority_min_rr
            and (
                signal.get("strategy_tier") == "TOP"
                or signal.get("notify")
                or signal.get("setup") in TOP_SETUPS
            )
        )

    def _priority_label(self, signal: dict) -> str:
        conf = signal.get("confidence", 0)
        if conf >= 90:
            return "MAX WIN"
        if conf >= 85 and signal.get("notify"):
            return "DEF BUY"
        return signal.get("rr_label", "SCALP")

    def _assign_priority(self, signal: dict, settings, high_slots_left: int) -> tuple[dict, int]:
        """Return signal with priority fields and updated high_slots_left."""
        if self._qualifies_high_priority(signal, settings) and high_slots_left > 0:
            signal["priority_tier"] = "HIGH"
            signal["priority_label"] = self._priority_label(signal)
            return signal, high_slots_left - 1
        signal["priority_tier"] = "NORMAL"
        signal["priority_label"] = signal.get("rr_label", "")
        return signal, high_slots_left

    @property
    def high_priority_count_today(self) -> int:
        return self._high_priority_emitted_today

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
        from app.services.trading_control import is_trading_paused
        if is_trading_paused():
            return []
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
            if c.get("confidence", 0) > settings.live_min_confidence
        ]

        remaining_total = (
            max(0, settings.max_take_signals_per_day - len(self._emitted_today))
            if settings.max_take_signals_per_day > 0
            else settings.max_signals_per_scan
        )
        per_scan = min(settings.max_signals_per_scan, remaining_total)

        high_slots = max(
            0,
            settings.max_high_priority_signals_per_day - self._high_priority_emitted_today,
        )
        take_signals: list[dict] = []
        for sig in quality:
            if len(take_signals) >= per_scan:
                break
            sig, high_slots = self._assign_priority(sig, settings, high_slots)
            take_signals.append(sig)

        if take_signals:
            by_key = {self._signal_key(s): s for s in self._active_signals}
            for sig in take_signals:
                by_key[self._signal_key(sig)] = sig
            self._active_signals = list(by_key.values())
        self._prune_stale_active(settings.scalp_holding_minutes)
        self._notify_scan_complete(self._active_signals)

        for sig in take_signals:
            if self._take_count_today >= settings.max_take_signals_per_day:
                break
            key = self._signal_key(sig)
            sig["status"] = "LIVE"
            trade_id = save_signal(sig)
            if trade_id:
                sig["trade_id"] = trade_id
                self._take_count_today += 1
                self._emitted_today.add(f"{key}:{self._take_count_today}")
                if sig.get("priority_tier") == "HIGH":
                    self._high_priority_emitted_today += 1
                try:
                    from app.services.trade_executor import execute_signal, is_auto_trade_enabled

                    if is_auto_trade_enabled():
                        result = execute_signal(sig, trade_id)
                        sig["exchange_execute"] = result
                        if result.get("ok"):
                            sig["user_taken"] = True
                            sig["executed_on_exchange"] = True
                except Exception:
                    logger.exception("Auto-execute failed for %s", key)
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

        try:
            from app.services.trade_executor import execute_signal, is_auto_trade_enabled

            if is_auto_trade_enabled() or payload.get("force_exchange"):
                execute_signal(payload, trade_id, force=True)
        except Exception:
            logger.exception("Exchange execute on take failed")

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
        if body_pct < 0.25:
            return False
        vol = float(bar["volume"])
        avg_vol = float(df["volume"].tail(20).mean()) if len(df) >= 20 else vol
        if vol < avg_vol * 0.85:
            return False
        if direction == "bullish":
            return body > 0 and float(bar["close"]) > float(prev["high"])
        return body < 0 and float(bar["close"]) < float(prev["low"])

    def _setups_for_symbol(self, sym: WatchlistSymbol, disabled_setups: set[str]):
        """Fast movers: 1m buy-dip / sell-top only."""
        if sym.category in ("meme", "mover"):
            if DIP_TOP_SETUP not in disabled_setups:
                yield DIP_TOP_SETUP, None
            return
        for setup_name, fn in SETUP_FUNCTIONS.items():
            if setup_name in disabled_setups or setup_name in PERMANENTLY_DISABLED_SETUPS:
                continue
            if setup_name in SCALP_SETUPS:
                continue
            yield setup_name, fn

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
        entry_df = futures_client.candles_to_df(entry_candles)
        if len(entry_df) < 4:
            return []

        for setup_name, fn in self._setups_for_symbol(sym, disabled_setups):
            scalp_tight = setup_name in SCALP_SETUPS
            if scalp_tight:
                setup_results = dip_top_scalp(entry_df, sym.change_pct_24h)
                bar_for_sl = entry_df.iloc[-1]
                atr_val = float(bar_for_sl["close"]) * atr_p / 100.0 if atr_p > 0 else float(bar_for_sl["close"]) * 0.003
            else:
                setup_results = [fn(df)]
                bar_for_sl = bar_5m
                atr_val = float(bar_for_sl["close"]) * atr_p / 100.0 if atr_p > 0 else float(bar_for_sl["close"]) * 0.008

            for result in setup_results:
                if not result.fired or not result.stop_loss:
                    continue

                direction = "LONG" if result.direction == "bullish" else "SHORT"
                if self._in_cooldown(setup_name, sym.pair, direction):
                    continue

                decision = evaluate_trade_decision(setup_name, result, regime, sym.category)
                if not decision["can_take"]:
                    continue

                if not scalp_tight and not self._confirm_entry_1m(result.direction or "bullish", entry_candles):
                    continue

                entry = float(entry_df.iloc[-1]["close"])
                stop = normalize_stop_loss(
                    entry=entry,
                    direction=result.direction or "bullish",
                    proposed_stop=float(result.stop_loss),
                    bar_low=float(bar_for_sl["low"]),
                    bar_high=float(bar_for_sl["high"]),
                    swing_low=swing_low,
                    swing_high=swing_high,
                    atr=atr_val,
                    tier=sym.tier,
                    scalp_tight=scalp_tight,
                )
                risk = abs(entry - stop)
                if risk <= 0:
                    continue
                sign = 1 if direction == "LONG" else -1
                live_cap = get_live_capital_usdt(settings)
                confidence = decision["take_confidence"]

                plan = plan_crypto_futures(
                    symbol=sym.pair,
                    direction=direction,
                    entry=entry,
                    stop_loss=stop,
                    target_1=entry,
                    target_2=entry,
                    capital_usdt=live_cap,
                    risk_usdt=fixed_risk_usdt(settings),
                    risk_usdt_max=settings.risk_per_trade_usdt_max,
                    max_deploy_pct=per_trade_deploy_pct(live_cap, settings),
                    available_usdt=get_available_usdt(settings),
                    min_leverage_cap=min_leverage_for_capital(live_cap, confidence, settings),
                    max_leverage_cap=max_leverage_for_capital(live_cap, confidence, settings),
                    atr_pct=atr_p,
                    sl_basis=result.sl_basis,
                    scalp_mode=scalp_tight,
                )
                if not plan.can_afford:
                    continue
                if plan.max_loss_usdt > settings.risk_per_trade_usdt_max * 1.05:
                    continue

                rr = scalp_rr_for_confidence(confidence, settings)
                fee_est = round_trip_fee_usdt(plan.notional_usdt, settings)
                entry_drag = estimated_entry_drag_usdt(plan.notional_usdt, settings)
                t1, t2, tp_gross, tp_net = tp_price_from_rr(
                    entry, stop, sign, rr, plan.notional_usdt, settings,
                )

                min_conf = settings.mover_min_confidence if sym.category in ("meme", "mover") else settings.normal_min_confidence
                if confidence <= min_conf:
                    continue
                notify = confidence >= settings.notify_min_confidence or (
                    decision.get("strategy_tier") == "TOP" and confidence >= 78
                )
                rr_label = f"1:{rr:.0f}" if rr >= 1.0 else "1:1"

                signal = plan.to_dict()
                signal["target_1_price"] = t1
                signal["target_2_price"] = t2
                signal["max_loss_usdt"] = round(plan.max_loss_usdt, 3)
                signal["target_profit_usdt"] = round(tp_net, 3)
                signal["target_profit_gross_usdt"] = round(tp_gross, 3)
                signal["estimated_fees_usdt"] = round(fee_est + entry_drag, 3)
                signal["scalp_rr"] = rr
                hold_m = settings.scalp_holding_minutes
                scalp_label = "Buy dip" if result.direction == "bullish" else "Sell top"
                signal.update({
                    "setup": setup_name,
                    "confidence": confidence,
                    "notify": notify,
                    "rr_label": rr_label,
                    "signal_grade": decision.get("signal_grade", "A+" if notify else "A"),
                    "strategy_tier": decision.get("strategy_tier", "TOP" if setup_name in TOP_SETUPS else "STD"),
                    "decision_reason": decision["decision_reason"],
                    "regime": regime.regime.value,
                    "regime_summary": regime.summary,
                    "trend_direction": regime.trend_direction,
                    "sl_basis": result.sl_basis,
                    "chart_timeframe": ENTRY_TF,
                    "entry_timeframe": ENTRY_TF,
                    "validity_points": [
                        f"1m {scalp_label}: {result.reason}",
                        f"Entry TF: {ENTRY_TF} · max hold {hold_m} min · scan every 1m",
                        f"Market: {regime.summary} · 24h {sym.change_pct_24h:+.1f}%",
                        f"Trade decision: {decision['decision_reason']}",
                        f"Risk:Reward {rr_label} to T1 (SL-distance scalp)",
                        f"Confidence: {confidence}% — {'A+ NOTIFY' if notify else 'A quality scalp'}",
                        f"SL basis: {result.sl_basis}",
                        f"Leverage: {plan.leverage}x · Risk ₹{settings.risk_per_trade_inr:.0f} · {rr_label} net ~₹{round(tp_net * settings.usdt_to_inr):.0f} (costs ~₹{round((fee_est + entry_drag) * settings.usdt_to_inr):.0f})",
                        f"Fast mover · Funding: {round(funding, 4)}% · {sym.category.upper()}",
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
                    "target_pnl_inr": round(tp_net * settings.usdt_to_inr, 0),
                    "target_profit_inr": round(tp_net * settings.usdt_to_inr, 0),
                    "risk_reward": rr,
                    "margin_inr": round(plan.margin_usdt * settings.usdt_to_inr, 0),
                    "notional_inr": round(plan.notional_usdt * settings.usdt_to_inr, 0),
                    "position_inr": round(plan.margin_usdt * settings.usdt_to_inr * plan.leverage, 0),
                    "capital_inr": settings.crypto_capital_inr,
                    "risk_per_trade_inr": settings.risk_per_trade_inr,
                    "risk_per_trade_usdt": settings.risk_per_trade_usdt,
                    "take_profit_usdt": tp_net,
                    "spread_warning": sym.spread_pct > 0.1,
                    "trading_style": settings.trading_style,
                })
                results.append(signal)

        if not results:
            return []

        max_per_sym = 2 if sym.category in ("meme", "mover") else (3 if sym.pair in FOCUS_PAIRS else 2)

        def _top_setups(items: list[dict], limit: int) -> list[dict]:
            if not items:
                return []
            items.sort(key=lambda s: (
                SETUP_PRIORITY.get(s.get("setup", ""), 9),
                -s.get("confidence", 0),
                -s.get("risk_reward", 0),
            ))
            seen: set[str] = set()
            out: list[dict] = []
            for item in items:
                key = f"{item.get('setup')}:{item.get('direction')}"
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
                if len(out) >= limit:
                    break
            return out

        return _top_setups(results, max_per_sym)


crypto_scanner = CryptoScanner()
