"""Per-client paper wallet, Binance credentials, and auto-trade preferences."""

from __future__ import annotations

import base64
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, String, Text, select

from app.config import get_settings
from app.db.models import ClientAccount, get_session


def _secret() -> bytes:
    raw = (get_settings().client_data_secret or "scalptrack-client-dev-key").encode()
    return hashlib.sha256(raw).digest()


def _encrypt(plain: str) -> str:
    if not plain:
        return ""
    data = plain.encode()
    key = _secret()
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return base64.urlsafe_b64encode(xored).decode()


def _decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        xored = base64.urlsafe_b64decode(token.encode())
        key = _secret()
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(xored)).decode()
    except Exception:
        return ""


def ensure_tables() -> None:
    from app.db.models import init_db
    init_db()


def register_client(client_id: str | None = None) -> str:
    ensure_tables()
    cid = (client_id or "").strip() or str(uuid.uuid4())
    session = get_session()
    try:
        row = session.get(ClientAccount, cid)
        if not row:
            s = get_settings()
            row = ClientAccount(
                client_id=cid,
                paper_balance_usdt=s.paper_wallet_usdt,
                paper_enabled=True,
                live_auto_trade=False,
            )
            session.add(row)
            session.commit()
        return cid
    finally:
        session.close()


def get_client(client_id: str) -> ClientAccount | None:
    if not client_id:
        return None
    ensure_tables()
    session = get_session()
    try:
        return session.get(ClientAccount, client_id)
    finally:
        session.close()


def get_or_create_client(client_id: str) -> ClientAccount:
    register_client(client_id)
    row = get_client(client_id)
    assert row is not None
    return row


def save_client_credentials(
    client_id: str,
    *,
    api_key: str = "",
    api_secret: str = "",
    paper_enabled: bool | None = None,
    live_auto_trade: bool | None = None,
) -> dict:
    row = get_or_create_client(client_id)
    session = get_session()
    try:
        acc = session.get(ClientAccount, client_id)
        if not acc:
            return {"ok": False, "reason": "client not found"}
        if api_key:
            acc.api_key_enc = _encrypt(api_key.strip())
        if api_secret:
            acc.api_secret_enc = _encrypt(api_secret.strip())
        if paper_enabled is not None:
            acc.paper_enabled = paper_enabled
        if live_auto_trade is not None:
            acc.live_auto_trade = live_auto_trade
        acc.updated_at = datetime.now(timezone.utc)
        session.commit()
        return client_public_view(acc)
    finally:
        session.close()


def client_binance_keys(client_id: str) -> tuple[str, str] | None:
    row = get_client(client_id)
    if not row or not row.live_auto_trade:
        return None
    key = _decrypt(row.api_key_enc or "")
    secret = _decrypt(row.api_secret_enc or "")
    if not key or not secret:
        return None
    return key, secret


def get_paper_balance(client_id: str) -> float:
    row = get_or_create_client(client_id)
    return float(row.paper_balance_usdt or get_settings().paper_wallet_usdt)


def apply_paper_pnl(client_id: str, pnl_usdt: float) -> float:
    if not client_id:
        return get_settings().paper_wallet_usdt
    session = get_session()
    try:
        register_client(client_id)
        row = session.get(ClientAccount, client_id)
        if not row or not row.paper_enabled:
            return get_settings().paper_wallet_usdt
        row.paper_balance_usdt = max(0.0, float(row.paper_balance_usdt or 0) + float(pnl_usdt))
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        return float(row.paper_balance_usdt)
    finally:
        session.close()


def reset_paper_wallet(client_id: str) -> float:
    s = get_settings()
    session = get_session()
    try:
        register_client(client_id)
        acc = session.get(ClientAccount, client_id)
        if acc:
            acc.paper_balance_usdt = s.paper_wallet_usdt
            acc.updated_at = datetime.now(timezone.utc)
            session.commit()
        return s.paper_wallet_usdt
    finally:
        session.close()


def client_public_view(row: ClientAccount) -> dict:
    s = get_settings()
    has_keys = bool(row.api_key_enc and row.api_secret_enc)
    return {
        "client_id": row.client_id,
        "paper_enabled": bool(row.paper_enabled),
        "paper_balance_usdt": round(float(row.paper_balance_usdt or s.paper_wallet_usdt), 2),
        "paper_start_usdt": s.paper_wallet_usdt,
        "live_auto_trade": bool(row.live_auto_trade),
        "binance_keys_configured": has_keys,
        "trading_mode": "live" if row.live_auto_trade and has_keys else "paper",
    }
