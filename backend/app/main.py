import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import account, crypto, health, news, settings as settings_routes, signals, signals_ws
from app.config import get_settings
from app.db.models import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.services.binance_stream import price_stream

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting CryptoSignalApp (%s)", settings.app_env)
    init_db()
    from app.services.trade_analytics import purge_old_trades
    purge_old_trades()
    loop = asyncio.get_running_loop()
    signals_ws.broadcaster.start(loop)
    price_stream.start(loop)
    price_stream.on_price(signals_ws.broadcaster.on_price)
    from app.services.price_sync import sync_tracked_symbols
    sync_tracked_symbols()
    start_scheduler()
    yield
    price_stream.stop()
    stop_scheduler()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CryptoSignalApp API",
        description="Crypto futures signals — all coins, strict SL, leverage",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(signals.router)
    app.include_router(account.router)
    app.include_router(settings_routes.router)
    app.include_router(crypto.router)
    app.include_router(news.router)
    app.include_router(signals_ws.router)
    return app


app = create_app()
