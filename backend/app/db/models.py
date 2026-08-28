"""SQLite persistence for signal trades and account tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class SignalTrade(Base):
    __tablename__ = "signal_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), nullable=False, index=True)
    setup = Column(String(64), nullable=False)
    direction = Column(String(8), nullable=False)
    status = Column(String(16), default="OPEN", index=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    stop_loss_price = Column(Float, nullable=False)
    target_1_price = Column(Float, nullable=False)
    target_2_price = Column(Float, nullable=True)
    leverage = Column(Integer, default=1)
    quantity = Column(Float, default=0)
    margin_usdt = Column(Float, default=0)
    max_loss_usdt = Column(Float, default=0)
    target_profit_usdt = Column(Float, default=0)
    pnl_usdt = Column(Float, default=0)
    pnl_inr = Column(Float, default=0)
    confidence = Column(Integer, default=0)
    category = Column(String(16), default="alt")
    close_reason = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    closed_at = Column(DateTime, nullable=True)
    payload_json = Column(Text, default="{}")


class DailyPnlSnapshot(Base):
    """Daily rollup — kept after raw trades are purged (>7 days)."""
    __tablename__ = "daily_pnl_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(10), nullable=False, unique=True, index=True)
    total_trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    profit_inr = Column(Float, default=0)
    loss_inr = Column(Float, default=0)
    net_pnl_inr = Column(Float, default=0)
    equity_start_inr = Column(Float, default=0)
    equity_end_inr = Column(Float, default=0)
    outcome_sequence = Column(String(2000), default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SetupPerformance(Base):
    """Per-strategy profit stats — which setup wins/loses most."""
    __tablename__ = "setup_performance"

    setup = Column(String(64), primary_key=True)
    total_trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    total_profit_inr = Column(Float, default=0)
    total_loss_inr = Column(Float, default=0)
    net_pnl_inr = Column(Float, default=0)
    win_rate_pct = Column(Float, default=0)
    avg_win_inr = Column(Float, default=0)
    avg_loss_inr = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


_engine = None
_SessionLocal = None


def _build_engine():
    settings = get_settings()
    if settings.database_url:
        url = settings.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{settings.sqlite_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )


def database_kind() -> str:
    return "neon" if get_settings().database_url else "sqlite"


def init_db() -> None:
    global _engine, _SessionLocal
    _engine = _build_engine()
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()
