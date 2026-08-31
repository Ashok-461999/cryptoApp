"""Execute ScalpTrack signals as real Binance Futures orders."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import SignalTrade, get_session
from app.services.binance_trading_client import BinanceTradingClient, binance_trading, trading_client_for
from app.services.trading_fees import passes_fee_gate

logger = logging.getLogger(__name__)


def _payload(t: SignalTrade) -> dict:
    try:
        return json.loads(t.payload_json or "{}")
    except json.JSONDecodeError:
        return {}


def _save_payload(t: SignalTrade, payload: dict) -> None:
    t.payload_json = json.dumps(payload)


def is_auto_trade_enabled() -> bool:
    from app.services.trading_control import is_trading_paused
    s = get_settings()
    if is_trading_paused():
        return False
    return s.auto_execute_trades and binance_trading.is_configured()


def count_exchange_trades_today() -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        trades = session.scalars(select(SignalTrade).where(SignalTrade.created_at >= start)).all()
        return sum(1 for t in trades if _payload(t).get("executed_on_exchange"))
    finally:
        session.close()


def count_open_exchange_positions() -> int:
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade).where(SignalTrade.status == "OPEN")
        ).all()
        return sum(1 for t in trades if _payload(t).get("executed_on_exchange"))
    finally:
        session.close()


def _can_execute(signal: dict) -> tuple[bool, str]:
    from app.services.binance_account import get_live_capital_usdt, max_notional_for_wallet

    s = get_settings()
    if not is_auto_trade_enabled():
        return False, "auto_execute disabled or API keys missing"
    if int(signal.get("confidence") or 0) < s.auto_execute_min_confidence:
        return False, "confidence below auto_execute_min_confidence"
    if count_exchange_trades_today() >= s.max_exchange_trades_per_day:
        return False, "daily exchange trade cap reached"
    if count_open_exchange_positions() >= s.max_exchange_open_positions:
        return False, "max open exchange positions reached"
    bal = bx.get_usdt_balance()
    margin = float(signal.get("margin_usdt") or 0)
    if margin > 0 and bal < margin * 1.05:
        return False, f"insufficient USDT balance ({bal:.2f} < margin {margin:.2f})"
    if margin > bal * 0.35:
        return False, f"margin ${margin:.2f} exceeds 35% of wallet (${bal:.2f})"
    wallet = get_live_capital_usdt(s)
    if wallet < 25:
        return False, f"wallet ${wallet:.2f} too low — deposit or pause until above $25"
    max_loss = float(signal.get("max_loss_usdt") or 0)
    if max_loss > s.risk_per_trade_usdt_max * 1.05:
        return False, f"max loss ${max_loss:.2f} exceeds ${s.risk_per_trade_usdt_max:.2f} cap"
    notional = float(signal.get("notional_usdt") or 0)
    if notional <= 0 and margin > 0:
        notional = margin * int(signal.get("leverage") or 1)
    cap = max_notional_for_wallet(get_live_capital_usdt(s), s)
    if notional > cap * 1.02:
        return False, f"notional ${notional:.2f} exceeds wallet cap ${cap:.2f}"
    tp_net = float(signal.get("target_profit_usdt") or 0)
    if notional > 0 and not passes_fee_gate(tp_net, notional, s):
        return False, "expected profit too small vs fees"
    return True, "ok"


def _place_brackets(
    symbol: str,
    direction: str,
    fill_price: float,
    fill_qty: float,
    sl: float,
    tp: float,
    *,
    position_side: str | None,
    client: BinanceTradingClient | None = None,
) -> tuple[dict, dict]:
    """Place SL+TP with distance adjust + retry (avoids instant market-close churn)."""
    bx = client or binance_trading
    exit_side = "SELL" if direction == "LONG" else "BUY"
    last_err: BinanceTradingError | None = None
    for widen in (0.0, 0.15, 0.35):
        adj_sl, adj_tp = bx.adjust_bracket_prices(
            symbol, direction, fill_price, sl, tp, widen_pct=widen,
        )
        try:
            sl_order = bx.place_stop_market(
                symbol, exit_side, adj_sl, fill_qty, position_side=position_side,
            )
            tp_order = bx.place_take_profit_market(
                symbol, exit_side, adj_tp, fill_qty, position_side=position_side,
            )
            return sl_order, tp_order
        except BinanceTradingError as exc:
            last_err = exc
            if "immediately trigger" not in str(exc).lower():
                raise
            logger.warning("Bracket widen %.2f%% for %s: %s", widen, symbol, exc)
    if last_err:
        raise last_err
    raise BinanceTradingError("Failed to place brackets")


def execute_signal(signal: dict, trade_id: int, *, force: bool = False, client_id: str | None = None) -> dict:
    """Open a Binance Futures position with SL + TP bracket orders."""
    bx = trading_client_for(client_id)
    if force:
        if not bx.is_configured():
            return {"ok": False, "reason": "Binance API keys not configured"}
        ok, reason = True, "manual take"
    else:
        ok, reason = _can_execute(signal)
    if not ok:
        logger.info("Skip exchange execute #%s: %s", trade_id, reason)
        return {"ok": False, "reason": reason}

    symbol = signal.get("symbol", "")
    direction = (signal.get("direction") or "LONG").upper()
    leverage = int(signal.get("leverage") or 25)
    quantity = float(signal.get("quantity") or 0)
    sl = float(signal.get("stop_loss_price") or 0)
    tp = float(signal.get("target_1_price") or 0)

    if quantity <= 0 or sl <= 0 or tp <= 0:
        return {"ok": False, "reason": "invalid quantity or levels"}

    entry_side = "BUY" if direction == "LONG" else "SELL"
    exit_side = "SELL" if direction == "LONG" else "BUY"

    session = get_session()
    try:
        trade = session.get(SignalTrade, trade_id)
        if not trade:
            return {"ok": False, "reason": "trade not found"}
        payload = _payload(trade)
        if payload.get("executed_on_exchange"):
            return {"ok": True, "reason": "already executed", "duplicate": True}

        try:
            bx.ensure_one_way_mode()
            bx.set_isolated_margin(symbol)
            actual_lev = bx.set_leverage(symbol, leverage)
            position_side = direction if bx.is_hedge_mode() else None
            entry_order = bx.place_market_order(
                symbol, entry_side, quantity, position_side=position_side
            )
            fill_qty = float(entry_order.get("executedQty") or quantity)
            fill_price = float(entry_order.get("avgPrice") or entry_order.get("price") or signal.get("entry_price") or 0)
            payload.update({
                "exchange_entry_filled": True,
                "binance_entry_order_id": entry_order.get("orderId"),
                "actual_fill_price": fill_price,
                "actual_quantity": fill_qty,
            })
            _save_payload(trade, payload)
            session.commit()

            sl_order, tp_order = _place_brackets(
                symbol, direction, fill_price, fill_qty, sl, tp, position_side=position_side, client=bx,
            )
            if client_id:
                payload["client_id"] = client_id

            payload.update({
                "executed_on_exchange": True,
                "user_taken": True,
                "binance_entry_order_id": entry_order.get("orderId"),
                "binance_sl_order_id": sl_order.get("algoId") or sl_order.get("orderId"),
                "binance_tp_order_id": tp_order.get("algoId") or tp_order.get("orderId"),
                "actual_fill_price": fill_price,
                "actual_quantity": fill_qty,
                "actual_leverage": actual_lev,
                "exchange_executed_at": datetime.now(timezone.utc).isoformat(),
            })
            if fill_price > 0:
                trade.entry_price = fill_price
            trade.quantity = fill_qty
            _save_payload(trade, payload)
            session.commit()
            logger.info(
                "Exchange OPEN %s %s qty=%s entry=%s sl=%s tp=%s",
                direction, symbol, fill_qty, fill_price, sl, tp,
            )
            return {"ok": True, "entry_order_id": entry_order.get("orderId"), "fill_price": fill_price}
        except BinanceTradingError as exc:
            payload["exchange_error"] = str(exc)
            _save_payload(trade, payload)
            session.commit()
            logger.exception("Exchange execute failed trade #%s", trade_id)
            # Only flatten if entry filled but brackets could not be placed after retries
            if payload.get("exchange_entry_filled"):
                try:
                    bx.cancel_bracket_orders(
                        symbol,
                        sl_algo_id=payload.get("binance_sl_order_id"),
                        tp_algo_id=payload.get("binance_tp_order_id"),
                    )
                    logger.error("Unwinding naked position %s after bracket failure", symbol)
                    bx.close_position_market(symbol)
                except Exception:
                    logger.exception("Failed to unwind position after execute error for %s", symbol)
            return {"ok": False, "reason": str(exc)}
    finally:
        session.close()


def _had_exchange_activity(payload: dict) -> bool:
    return bool(
        payload.get("executed_on_exchange")
        or payload.get("exchange_entry_filled")
        or payload.get("binance_entry_order_id")
    )


def sync_exchange_on_close(trade_id: int, close_reason: str) -> dict:
    """Always cancel conditional SL/TP and close any leftover position."""
    session = get_session()
    try:
        trade = session.get(SignalTrade, trade_id)
        if not trade:
            return {"ok": False, "reason": "trade not found"}
        payload = _payload(trade)
        if not _had_exchange_activity(payload):
            return {"ok": False, "reason": "not on exchange"}

        symbol = trade.symbol
        try:
            binance_trading.cancel_bracket_orders(
                symbol,
                sl_algo_id=payload.get("binance_sl_order_id"),
                tp_algo_id=payload.get("binance_tp_order_id"),
            )
            close_order = binance_trading.close_position_market(symbol)
            payload["exchange_closed_at"] = datetime.now(timezone.utc).isoformat()
            payload["exchange_close_reason"] = close_reason
            payload["exchange_brackets_cancelled"] = True
            if close_order:
                payload["binance_close_order_id"] = close_order.get("orderId")
            _save_payload(trade, payload)
            session.commit()
            logger.info("Exchange SYNC CLOSE %s reason=%s", symbol, close_reason)
            return {"ok": True, "close_order_id": (close_order or {}).get("orderId")}
        except BinanceTradingError as exc:
            payload["exchange_close_error"] = str(exc)
            _save_payload(trade, payload)
            session.commit()
            return {"ok": False, "reason": str(exc)}
    finally:
        session.close()


def emergency_flatten_exchange() -> dict:
    """Cancel all conditional orders and close all positions (pause / safety)."""
    if not binance_trading.is_configured():
        return {"ok": False, "reason": "not configured"}
    algos = binance_trading.cancel_all_algo_orders_global()
    positions = binance_trading.flatten_all_positions()
    logger.warning("Emergency flatten: cancelled %d algos, closed %d positions", algos, positions)
    return {"ok": True, "algos_cancelled": algos, "positions_closed": positions}


def cleanup_orphan_exchange_orders() -> int:
    """Cancel conditional orders left after app-side closes."""
    if not binance_trading.is_configured():
        return 0
    session = get_session()
    try:
        open_trades = session.scalars(
            select(SignalTrade).where(SignalTrade.status == "OPEN")
        ).all()
        open_symbols = {t.symbol for t in open_trades}
        open_algo_ids = set()
        for t in open_trades:
            p = _payload(t)
            for key in ("binance_sl_order_id", "binance_tp_order_id"):
                if p.get(key):
                    open_algo_ids.add(int(p[key]))
    finally:
        session.close()

    cancelled = 0
    for order in binance_trading.list_open_algo_orders():
        sym = order.get("symbol", "")
        aid = order.get("algoId")
        if sym in open_symbols and aid in open_algo_ids:
            continue
        if aid:
            binance_trading.cancel_algo_order(aid)
            cancelled += 1
    return cancelled


def close_exchange_trade(trade_id: int, reason: str = "APP_CLOSE") -> dict:
    """Market-close Binance position and cancel bracket orders."""
    return sync_exchange_on_close(trade_id, reason)


def on_trade_closed(trade_id: int, close_reason: str) -> None:
    """Always cancel conditional SL/TP on Binance when app closes a trade."""
    sync_exchange_on_close(trade_id, close_reason)
