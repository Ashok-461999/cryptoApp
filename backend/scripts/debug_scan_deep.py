"""Trace why dip/top setups don't become signals."""
from app.config import get_settings
from app.services.binance_account import (
    fixed_risk_usdt,
    get_available_usdt,
    get_live_capital_usdt,
    max_leverage_for_capital,
    max_notional_for_wallet,
    min_leverage_for_capital,
    per_trade_deploy_pct,
    scalp_rr_for_confidence,
)
from app.services.crypto_futures_client import futures_client
from app.services.crypto_watchlist import get_scan_symbol_order, refresh_watchlist
from app.services.trade_analytics import get_disabled_setups
from app.services.trading_fees import estimated_entry_drag_usdt, passes_fee_gate, round_trip_fee_usdt
from app.signals.crypto_scanner import crypto_scanner
from app.signals.indicators import atr_pct, ensure_ohlcv
from app.signals.market_structure import swing_high_low
from app.signals.momentum_scalp import SETUP_NAME as DIP_TOP_SETUP, dip_top_scalp
from app.signals.position_sizing_crypto import plan_crypto_futures
from app.signals.regime import detect_regime
from app.signals.scalp_levels import build_scalp_targets, validate_scalp_levels
from app.signals.sl_levels import normalize_stop_loss
from app.signals.trade_decision import evaluate_trade_decision

refresh_watchlist()
settings = get_settings()
disabled = get_disabled_setups()

for sym in get_scan_symbol_order()[:15]:
    struct_candles = futures_client.get_futures_candles(sym.pair, "5m", 120)
    entry_candles = futures_client.get_futures_candles(sym.pair, "1m", 60)
    if len(struct_candles) < 60 or len(entry_candles) < 4:
        continue
    df = futures_client.candles_to_df(struct_candles)
    entry_df = ensure_ohlcv(futures_client.candles_to_df(entry_candles))
    regime = detect_regime(df)
    atr_p = atr_pct(df)
    swing_high, swing_low = swing_high_low(df)
    bar_for_sl = entry_df.iloc[-1]
    atr_val = float(bar_for_sl["close"]) * atr_p / 100.0 if atr_p > 0 else float(bar_for_sl["close"]) * 0.003

    for result in dip_top_scalp(entry_df, sym.change_pct_24h):
        direction = "LONG" if result.direction == "bullish" else "SHORT"
        scalp_type = (result.metadata or {}).get("scalp_type", "")
        if not crypto_scanner._confirm_scalp_reversal(result.direction or "bullish", entry_df):
            print(sym.pair, direction, "BLOCK confirm_scalp_reversal")
            continue
        decision = evaluate_trade_decision(DIP_TOP_SETUP, result, regime, sym.category)
        if not decision["can_take"]:
            print(sym.pair, direction, "BLOCK decision:", decision["decision_reason"])
            continue
        entry = float(entry_df.iloc[-1]["close"])
        stop = normalize_stop_loss(
            entry=entry, direction=result.direction or "bullish",
            proposed_stop=float(result.stop_loss),
            bar_low=float(bar_for_sl["low"]), bar_high=float(bar_for_sl["high"]),
            swing_low=swing_low, swing_high=swing_high, atr=atr_val,
            tier=sym.tier, scalp_tight=True,
        )
        confidence = decision["take_confidence"]
        live_cap = get_live_capital_usdt(settings)
        plan = plan_crypto_futures(
            symbol=sym.pair, direction=direction, entry=entry, stop_loss=stop,
            target_1=entry, target_2=entry, capital_usdt=live_cap,
            risk_usdt=fixed_risk_usdt(settings), risk_usdt_max=settings.risk_per_trade_usdt_max,
            max_deploy_pct=per_trade_deploy_pct(live_cap, settings),
            available_usdt=get_available_usdt(settings),
            min_leverage_cap=min_leverage_for_capital(live_cap, confidence, settings),
            max_leverage_cap=max_leverage_for_capital(live_cap, confidence, settings),
            max_notional_cap=max_notional_for_wallet(live_cap, settings),
            atr_pct=atr_p, sl_basis=result.sl_basis, scalp_mode=True,
        )
        if not plan.can_afford:
            print(sym.pair, direction, "BLOCK can_afford:", plan.reason)
            continue
        rr = scalp_rr_for_confidence(confidence, settings)
        targets = build_scalp_targets(entry, stop, direction, rr, plan.notional_usdt, settings)
        if targets is None:
            print(sym.pair, direction, "BLOCK invalid targets")
            continue
        t1, t2, tp_gross, tp_net = targets
        if not validate_scalp_levels(entry, stop, t1, direction):
            print(sym.pair, direction, "BLOCK validate_scalp_levels")
            continue
        if not passes_fee_gate(tp_net, plan.notional_usdt, settings):
            fees = round_trip_fee_usdt(plan.notional_usdt) + estimated_entry_drag_usdt(plan.notional_usdt)
            print(sym.pair, direction, f"BLOCK fee_gate tp_net={tp_net:.3f} fees={fees:.3f}")
            continue
        min_conf = settings.mover_min_confidence if sym.category in ("meme", "mover") else settings.normal_min_confidence
        if confidence <= min_conf:
            print(sym.pair, direction, f"BLOCK confidence {confidence} <= {min_conf}")
            continue
        print(sym.pair, direction, f"PASS conf={confidence} tp_net={tp_net:.3f} {scalp_type}")
