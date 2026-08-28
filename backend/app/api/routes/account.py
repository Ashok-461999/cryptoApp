from fastapi import APIRouter

from app.services.signal_tracker import get_account_stats, get_trade_history

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/stats")
def account_stats():
    """Equity, drawdown, win rate for ₹20k / $240 capital."""
    return get_account_stats()


@router.get("/trades")
def trade_history(limit: int = 100):
    return {"trades": get_trade_history(limit)}
