"""Tests for Alpha Engine confluence and gates."""

import pandas as pd

from app.signals.alpha_engine import (
    compute_confluence,
    funding_blocks_trade,
    htf_bias,
    layered_targets,
)
from app.signals.regime import Regime, RegimeSnapshot
from app.signals.schemas import SetupResult


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low": [c * 0.995 for c in closes],
        "close": closes,
        "volume": [1000.0] * len(closes),
    })


def test_htf_bias_trending_up():
    closes = [100 + i * 0.5 for i in range(60)]
    bias = htf_bias(_ohlcv(closes))
    assert bias.bias in ("bullish", "neutral", "bearish")
    assert bias.summary


def test_confluence_requires_categories():
    regime = RegimeSnapshot(Regime.TRENDING, 30.0, 40.0, "bullish", "Trending")
    result = SetupResult(
        setup_name="amd_model",
        fired=True,
        direction="bullish",
        entry=100.0,
        stop_loss=99.0,
        targets=[102.0],
        reason="AMD sweep",
        metadata={"structure_break": True, "sweep": True},
    )
    htf = htf_bias(_ohlcv([100 + i * 0.3 for i in range(60)]))
    conf = compute_confluence("amd_model", result, regime, htf, "LONG", 2.0)
    assert conf.score >= 3
    assert len(conf.categories) >= 2


def test_funding_blocks_crowded_long():
    reason = funding_blocks_trade("LONG", 0.12)
    assert reason is not None
    assert "crowded" in reason.lower()


def test_layered_targets_long():
    t1, t2, t3 = layered_targets(100.0, 99.0, "LONG")
    assert t1 == 102.0
    assert t3 == 104.0
