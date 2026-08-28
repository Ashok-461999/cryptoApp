from fastapi import APIRouter, Query

from app.services.market_news import fetch_market_news

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/market")
def get_market_news(limit: int = Query(50, ge=10, le=80)):
    """Global crypto + macro news with affected-market tags."""
    return fetch_market_news(limit)
