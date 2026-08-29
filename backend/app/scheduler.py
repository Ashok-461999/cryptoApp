import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.services.crypto_watchlist import refresh_top_movers, refresh_watchlist
from app.services.signal_tracker import expire_stale_open_trades, reconcile_open_trades
from app.services.trade_analytics import purge_old_trades, rebuild_daily_snapshot
from app.signals.crypto_scanner import crypto_scanner

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_scan():
    try:
        from app.services.trading_control import is_trading_paused
        if is_trading_paused():
            return
        signals = crypto_scanner.scan_all()
        logger.info("Scan complete — %d TAKE signals", len(signals))
    except Exception:
        logger.exception("Scheduled scan failed")


def _run_watchlist_refresh():
    try:
        wl = refresh_watchlist()
        logger.info("Watchlist refresh — %d symbols", wl.total_count)
    except Exception:
        logger.exception("Watchlist refresh failed")


def _run_reconcile():
    try:
        closed = reconcile_open_trades()
        if closed:
            logger.info("Reconciled %d trades (WIN/LOSS)", len(closed))
    except Exception:
        logger.exception("Trade reconcile failed")


def _expire_trades():
    settings = get_settings()
    n = expire_stale_open_trades(settings.scalp_holding_minutes)
    if n:
        logger.info("Expired %d stale OPEN trades", n)


def _run_purge():
    try:
        purge_old_trades()
    except Exception:
        logger.exception("Trade purge failed")


def _snapshot_yesterday():
    try:
        from datetime import datetime, timedelta, timezone
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        rebuild_daily_snapshot(yesterday)
    except Exception:
        logger.exception("Daily snapshot failed")


def _run_movers_refresh():
    try:
        movers = refresh_top_movers(force=True)
        logger.info("Top movers refreshed — %d volatile coins (3h cycle)", len(movers))
        from app.services.mover_tracker import refresh_mover_trackers
        refresh_mover_trackers(movers, force=True)
    except Exception:
        logger.exception("Top movers refresh failed")


def _run_levels_refresh():
    """Refresh BTC/Gold + meme Entry/SL/TP1 every 10–15 min."""
    try:
        from app.services.focus_tracker import refresh_focus_trackers
        from app.services.mover_tracker import refresh_mover_trackers
        refresh_focus_trackers(force=True)
        refresh_mover_trackers(force=True)
        logger.info("Trade levels refreshed (BTC/Gold + movers)")
    except Exception:
        logger.exception("Levels refresh failed")


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    _scheduler = BackgroundScheduler()

    _scheduler.add_job(
        _run_watchlist_refresh,
        CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="watchlist_refresh",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_movers_refresh,
        IntervalTrigger(hours=settings.mover_refresh_hours),
        id="movers_refresh",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_levels_refresh,
        IntervalTrigger(minutes=settings.mover_levels_refresh_minutes),
        id="levels_refresh",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_scan,
        IntervalTrigger(seconds=settings.scan_interval_seconds),
        id="crypto_scan",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_reconcile,
        IntervalTrigger(seconds=15),
        id="reconcile_trades",
        replace_existing=True,
    )
    _scheduler.add_job(
        _expire_trades,
        IntervalTrigger(minutes=5),
        id="expire_trades",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_purge,
        CronTrigger(hour=1, minute=30, timezone="UTC"),
        id="purge_old_trades",
        replace_existing=True,
    )
    _scheduler.add_job(
        _snapshot_yesterday,
        CronTrigger(hour=0, minute=5, timezone="UTC"),
        id="daily_snapshot",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started — scan every %ds", settings.scan_interval_seconds)

    # Initial load in background thread so startup isn't blocked
    import threading
    threading.Thread(target=_run_movers_refresh, daemon=True).start()
    threading.Thread(target=_run_watchlist_refresh, daemon=True).start()
    threading.Thread(target=_run_levels_refresh, daemon=True).start()
    threading.Thread(target=_run_scan, daemon=True).start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
