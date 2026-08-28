"""Daily PnL snapshots, setup performance, and 7-day trade purge."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.config import get_settings
from app.db.models import DailyPnlSnapshot, SetupPerformance, SignalTrade, get_session

logger = logging.getLogger(__name__)

_SETUP_LABELS = {
    "structure_fib_sweep": "Structure+Fib+Sweep",
    "liquidity_sweep": "Liquidity Sweep",
    "amd_model": "AMD Model",
    "ifvg_reversal": "IFVG",
    "order_flow": "Order Flow",
    "anchored_vwap": "Anchored VWAP",
    "volume_profile": "Volume Profile",
    "supply_demand": "Supply & Demand",
    "fvg_retest": "FVG Retest",
    "fibonacci_retrace": "Fibonacci",
    "structure_reversal": "Structure Reversal",
    "orb_breakout": "ORB Breakout",
}

_disabled_cache: dict = {"at": None, "setups": set()}


def _utc_date(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _effective_outcome(t: SignalTrade) -> str | None:
    if t.close_reason in ("TIMEOUT_BELOW_TARGET", "TIMEOUT_PROFIT"):
        pnl = float(t.pnl_inr or 0)
        settings = get_settings()
        min_win = float(getattr(settings, "min_win_close_inr", 0) or settings.take_profit_inr)
        if pnl >= min_win:
            return "W"
        return "L"
    if t.status == "WIN":
        return "W"
    if t.status == "LOSS":
        return "L"
    if t.status == "EXPIRED":
        pnl = float(t.pnl_inr or 0)
        if pnl > 0:
            return "W"
        if pnl < 0:
            return "L"
    return None


def rebuild_daily_snapshot(trade_date: str) -> None:
    """Rebuild one day's rollup from raw trades (ordered W/L sequence preserved)."""
    settings = get_settings()
    start = datetime.strptime(trade_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade)
            .where(SignalTrade.created_at >= start, SignalTrade.created_at < end)
            .order_by(SignalTrade.created_at.asc())
        ).all()
        closed = [t for t in trades if _effective_outcome(t)]
        seq = [_effective_outcome(t) for t in closed]
        wins = sum(1 for s in seq if s == "W")
        losses = sum(1 for s in seq if s == "L")
        profit_inr = sum(float(t.pnl_inr or 0) for t in closed if float(t.pnl_inr or 0) > 0)
        loss_inr = sum(float(t.pnl_inr or 0) for t in closed if float(t.pnl_inr or 0) < 0)
        net = profit_inr + loss_inr

        prior = session.scalar(
            select(func.coalesce(func.sum(DailyPnlSnapshot.net_pnl_inr), 0)).where(
                DailyPnlSnapshot.trade_date < trade_date
            )
        ) or 0
        equity_start = settings.crypto_capital_inr + float(prior)
        equity_end = equity_start + net

        row = session.scalar(
            select(DailyPnlSnapshot).where(DailyPnlSnapshot.trade_date == trade_date)
        )
        if row is None:
            row = DailyPnlSnapshot(trade_date=trade_date)
            session.add(row)
        row.total_trades = len(closed)
        row.wins = wins
        row.losses = losses
        row.profit_inr = round(profit_inr, 0)
        row.loss_inr = round(loss_inr, 0)
        row.net_pnl_inr = round(net, 0)
        row.equity_start_inr = round(equity_start, 0)
        row.equity_end_inr = round(equity_end, 0)
        row.outcome_sequence = ",".join(seq)
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed daily snapshot for %s", trade_date)
    finally:
        session.close()


def record_setup_result(trade: SignalTrade) -> None:
    """Increment setup performance when a trade closes."""
    outcome = _effective_outcome(trade)
    if not outcome:
        return
    pnl = float(trade.pnl_inr or 0)
    setup = trade.setup or "unknown"
    session = get_session()
    try:
        row = session.get(SetupPerformance, setup)
        if row is None:
            row = SetupPerformance(setup=setup)
            session.add(row)
        row.total_trades = (row.total_trades or 0) + 1
        if outcome == "W":
            row.wins = (row.wins or 0) + 1
            row.total_profit_inr = (row.total_profit_inr or 0) + max(pnl, 0)
        else:
            row.losses = (row.losses or 0) + 1
            row.total_loss_inr = (row.total_loss_inr or 0) + min(pnl, 0)
        row.net_pnl_inr = (row.total_profit_inr or 0) + (row.total_loss_inr or 0)
        closed = (row.wins or 0) + (row.losses or 0)
        row.win_rate_pct = round((row.wins or 0) / closed * 100, 1) if closed else 0
        row.avg_win_inr = round((row.total_profit_inr or 0) / max(row.wins or 0, 1), 0)
        row.avg_loss_inr = round((row.total_loss_inr or 0) / max(row.losses or 0, 1), 0)
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        clear_disabled_setups_cache()
    except Exception:
        session.rollback()
        logger.exception("Setup performance update failed")
    finally:
        session.close()


def on_trade_closed(trade: SignalTrade) -> None:
    record_setup_result(trade)
    if trade.created_at:
        rebuild_daily_snapshot(_utc_date(trade.created_at))


def purge_old_trades() -> int:
    """Snapshot then delete raw trades older than retention window."""
    settings = get_settings()
    days = max(1, settings.history_retention_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    session = get_session()
    try:
        old_trades = session.scalars(
            select(SignalTrade).where(SignalTrade.created_at < cutoff)
        ).all()
        for d in {_utc_date(t.created_at) for t in old_trades if t.created_at}:
            rebuild_daily_snapshot(d)
        result = session.execute(delete(SignalTrade).where(SignalTrade.created_at < cutoff))
        session.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info("Purged %d trades older than %d days", deleted, days)
        return deleted
    except Exception:
        session.rollback()
        logger.exception("Trade purge failed")
        return 0
    finally:
        session.close()


def get_daily_pnl_history(limit: int = 30) -> list[dict]:
    session = get_session()
    try:
        rows = session.scalars(
            select(DailyPnlSnapshot).order_by(DailyPnlSnapshot.trade_date.desc()).limit(limit)
        ).all()
        return [
            {
                "date": r.trade_date,
                "total_trades": r.total_trades,
                "wins": r.wins,
                "losses": r.losses,
                "profit_inr": r.profit_inr,
                "loss_inr": r.loss_inr,
                "net_pnl_inr": r.net_pnl_inr,
                "equity_end_inr": r.equity_end_inr,
                "outcome_sequence": r.outcome_sequence or "",
            }
            for r in rows
        ]
    finally:
        session.close()


def get_disabled_setups() -> set[str]:
    """Setups with enough history and poor win rate — skip on next scans."""
    from datetime import datetime, timedelta, timezone

    global _disabled_cache
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cached_at = _disabled_cache.get("at")
    if cached_at and (now - cached_at) < timedelta(minutes=2):
        return set(_disabled_cache.get("setups") or set())

    min_trades = max(3, settings.setup_disable_min_trades)
    max_wr = settings.setup_disable_max_win_rate
    disabled: set[str] = set()
    from app.signals.trade_decision import PERMANENTLY_DISABLED_SETUPS
    disabled |= PERMANENTLY_DISABLED_SETUPS
    session = get_session()
    try:
        rows = session.scalars(select(SetupPerformance)).all()
        for r in rows:
            closed = (r.wins or 0) + (r.losses or 0)
            if closed < min_trades:
                continue
            wr = float(r.win_rate_pct or 0)
            losses = r.losses or 0
            wins = r.wins or 0
            net = float(r.net_pnl_inr or 0)
            if wr < max_wr or (net < 0 and losses >= wins * 2):
                disabled.add(r.setup)
    finally:
        session.close()

    _disabled_cache = {"at": now, "setups": disabled}
    if disabled:
        logger.info("Auto-disabled losing setups: %s", ", ".join(sorted(disabled)))
    return disabled


def clear_disabled_setups_cache() -> None:
    global _disabled_cache
    _disabled_cache = {"at": None, "setups": set()}


def get_setup_performance() -> list[dict]:
    session = get_session()
    try:
        rows = session.scalars(
            select(SetupPerformance).order_by(SetupPerformance.net_pnl_inr.desc())
        ).all()
        out = []
        for r in rows:
            tier = "high" if (r.net_pnl_inr or 0) > 0 and (r.win_rate_pct or 0) >= 50 else (
                "low" if (r.net_pnl_inr or 0) < 0 else "mid"
            )
            out.append({
                "setup": r.setup,
                "label": _SETUP_LABELS.get(r.setup, r.setup.replace("_", " ").title()),
                "total_trades": r.total_trades,
                "wins": r.wins,
                "losses": r.losses,
                "total_profit_inr": round(r.total_profit_inr or 0, 0),
                "total_loss_inr": round(r.total_loss_inr or 0, 0),
                "net_pnl_inr": round(r.net_pnl_inr or 0, 0),
                "win_rate_pct": r.win_rate_pct,
                "avg_win_inr": r.avg_win_inr,
                "avg_loss_inr": r.avg_loss_inr,
                "tier": tier,
            })
        return out
    finally:
        session.close()


def rebuild_all_setup_stats() -> None:
    """Full rebuild from remaining trades (after migration)."""
    session = get_session()
    try:
        trades = list(
            session.scalars(
                select(SignalTrade).where(SignalTrade.status.in_(("WIN", "LOSS", "EXPIRED")))
            ).all()
        )
        session.execute(delete(SetupPerformance))
        for t in trades:
            record_setup_result(t)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Setup stats rebuild failed")
    finally:
        session.close()


def total_historical_pnl_inr() -> float:
    """Sum of archived daily snapshots (days before live window)."""
    session = get_session()
    try:
        return float(
            session.scalar(select(func.coalesce(func.sum(DailyPnlSnapshot.net_pnl_inr), 0))) or 0
        )
    finally:
        session.close()
