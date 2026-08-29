"""Persisted trading on/off — pause scans and auto-execute from the app."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


def _state_path() -> Path:
    settings = get_settings()
    base = Path(settings.sqlite_path).parent
    base.mkdir(parents=True, exist_ok=True)
    return base / "trading_state.json"


def _read_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read trading state")
        return {}


def _write_state(data: dict) -> None:
    path = _state_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_trading_paused() -> bool:
    state = _read_state()
    if "paused" in state:
        return bool(state["paused"])
    return get_settings().trading_paused_default


def set_trading_paused(paused: bool, *, by: str = "app") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    state = {
        "paused": paused,
        "updated_at": now,
        "updated_by": by,
    }
    if paused:
        state["paused_at"] = now
    else:
        state["resumed_at"] = now
    _write_state(state)
    logger.info("Trading %s by %s", "PAUSED" if paused else "STARTED", by)
    return get_trading_status()


def get_trading_status() -> dict:
    paused = is_trading_paused()
    state = _read_state()
    return {
        "trading_paused": paused,
        "trading_active": not paused,
        "paused_at": state.get("paused_at"),
        "resumed_at": state.get("resumed_at"),
        "updated_at": state.get("updated_at"),
        "updated_by": state.get("updated_by"),
        "status_label": "PAUSED" if paused else "RUNNING",
    }
