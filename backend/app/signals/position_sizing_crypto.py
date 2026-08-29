"""Crypto futures position sizing with strict SL, leverage, and liquidation safety."""

from __future__ import annotations

from dataclasses import dataclass

# Tier A — majors (always scan)
TIER_A_SYMBOLS = frozenset({"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "LINK"})

# Tier B — meme / high vol (examples; any meme passing volume filter is tier B)
TIER_B_MEME = frozenset({
    "DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI", "MEME", "BOME", "NEIRO", "POPCAT",
    "1000PEPE", "1000BONK", "1000FLOKI", "1000SHIB", "TRUMP", "PNUT", "MOODENG", "GOAT",
    "TURBO", "BRETT", "TOSHI", "MEW", "CHILLGUY", "FARTCOIN", "AI16Z", "ACT", "HIPPO",
    "MUBARAK", "TST", "BAN", "ARC", "VINE", "PIPPIN", "SWARMS", "GIGA", "MELANIA", "ANIME",
    "VIRTUAL", "AIXBT", "KOMA", "DEGEN", "CHEEMS", "SUNDOG", "PEOPLE", "LADYS", "MYRO",
})

TIER_DEFAULT_LEV = {"A": 40, "B": 35, "C": 30, "D": 35}
TIER_MAX_LEV = {"A": 40, "B": 40, "C": 35, "D": 40}
MIN_LEVERAGE = 5

# SL distance limits (% of entry)
SL_MIN_PCT = 0.6
SL_MIN_PCT_SCALP = 0.18
SL_MAX_PCT_MAJORS = 2.5
SL_MAX_PCT_MEME = 5.0
SL_MAX_PCT_SCALP = 0.55


@dataclass
class CryptoFuturesPlan:
    symbol: str
    direction: str
    leverage: int
    max_leverage: int
    quantity: float
    entry_price: float
    stop_loss_price: float
    target_1_price: float
    target_2_price: float
    liquidation_price: float
    margin_usdt: float
    max_loss_usdt: float
    target_profit_usdt: float
    notional_usdt: float
    risk_percent: float
    can_afford: bool
    strict_sl_rule: str
    trade_plan: str
    reason: str
    stop_loss_pct: float = 0.0
    target_1_pct: float = 0.0
    target_2_pct: float = 0.0
    risk_reward: float = 0.0
    liquidation_buffer_pct: float = 0.0
    tier: str = "C"
    sl_type: str = "HARD"
    sl_basis: str = "setup_structure"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "setup": getattr(self, "setup", ""),
            "trade_decision": "TAKE" if self.can_afford else "NO_TRADE",
            "confidence": getattr(self, "confidence", 0),
            "entry_price": self.entry_price,
            "stop_loss_price": self.stop_loss_price,
            "target_1_price": self.target_1_price,
            "target_2_price": self.target_2_price,
            "stop_loss_pct": round(self.stop_loss_pct, 2),
            "target_1_pct": round(self.target_1_pct, 2),
            "target_2_pct": round(self.target_2_pct, 2),
            "risk_reward": round(self.risk_reward, 2),
            "strict_sl_rule": self.strict_sl_rule,
            "sl_type": self.sl_type,
            "sl_basis": self.sl_basis,
            "leverage": self.leverage,
            "max_leverage_allowed": self.max_leverage,
            "liquidation_price": self.liquidation_price,
            "liquidation_buffer_pct": round(self.liquidation_buffer_pct, 1),
            "quantity": self.quantity,
            "margin_usdt": round(self.margin_usdt, 2),
            "notional_usdt": round(self.notional_usdt, 2),
            "max_loss_usdt": round(self.max_loss_usdt, 2),
            "target_profit_usdt": round(self.target_profit_usdt, 2),
            "risk_percent": self.risk_percent,
            "can_afford": self.can_afford,
            "trade_plan": self.trade_plan,
            "reason": self.reason,
            "tier": self.tier,
        }


def classify_tier(symbol: str) -> str:
    base = symbol.upper().replace("USDT", "")
    if base in TIER_A_SYMBOLS:
        return "A"
    if base in TIER_B_MEME or any(m in base for m in ("PEPE", "BONK", "FLOKI", "SHIB", "MEME", "WIF", "DOGE")):
        return "D"
    if base in {"SOL", "BNB", "LINK", "AVAX", "XRP", "ADA"}:
        return "B"
    return "C"


def liquidation_price(entry: float, leverage: int, direction: str) -> float:
    """Approximate liquidation price (maintenance margin ~0.4%)."""
    if leverage <= 0 or entry <= 0:
        return 0.0
    maint = 0.004
    if direction.upper() == "LONG":
        return entry * (1 - 1 / leverage + maint)
    return entry * (1 + 1 / leverage - maint)


def liquidation_too_close(
    entry: float,
    stop: float,
    leverage: int,
    direction: str,
    min_buffer_mult: float = 2.0,
) -> bool:
    liq = liquidation_price(entry, leverage, direction)
    stop_dist = abs(entry - stop)
    if stop_dist <= 0:
        return True
    liq_dist = abs(entry - liq)
    return liq_dist < stop_dist * min_buffer_mult


def validate_stop_distance(
    entry: float,
    stop: float,
    tier: str,
    *,
    scalp_mode: bool = False,
) -> tuple[bool, str]:
    if not entry or not stop:
        return False, "Missing entry or stop"
    dist_pct = abs(entry - stop) / entry * 100
    min_sl = SL_MIN_PCT_SCALP if scalp_mode else SL_MIN_PCT
    if dist_pct < min_sl:
        return False, f"SL too tight ({dist_pct:.2f}% < {min_sl}%)"
    if scalp_mode:
        max_sl = SL_MAX_PCT_SCALP
    else:
        max_sl = SL_MAX_PCT_MEME if tier == "D" else SL_MAX_PCT_MAJORS
    if dist_pct > max_sl:
        return False, f"SL too wide ({dist_pct:.2f}% > {max_sl}%)"
    return True, "ok"


def suggest_leverage(
    symbol: str,
    atr_pct: float,
    stop_distance_pct: float,
    tier: str,
    entry: float,
    stop: float,
    direction: str,
    *,
    min_leverage_cap: int | None = None,
    max_leverage_cap: int | None = None,
) -> int:
    base = TIER_DEFAULT_LEV.get(tier, 40)
    if max_leverage_cap is not None:
        base = max_leverage_cap
    if min_leverage_cap is not None:
        base = max(base, min_leverage_cap)
    if atr_pct > 5.0:
        base -= 5
    elif atr_pct > 3.0:
        base -= 3
    if stop_distance_pct > 3.0:
        base = min(base, max_leverage_cap or 40)
    max_lev = TIER_MAX_LEV.get(tier, 50)
    if max_leverage_cap is not None:
        max_lev = min(max_lev, max_leverage_cap)
    floor = min_leverage_cap if min_leverage_cap is not None else MIN_LEVERAGE
    lev = min(max(base, floor), max_lev)
    while lev > floor and liquidation_too_close(entry, stop, lev, direction):
        lev -= 1
    return max(lev, floor)


def plan_crypto_futures(
    symbol: str,
    direction: str,
    entry: float,
    stop_loss: float,
    target_1: float,
    target_2: float,
    capital_usdt: float,
    risk_percent: float = 1.0,
    max_deploy_pct: float = 35.0,
    atr_pct: float = 2.0,
    sl_basis: str = "setup_structure",
    scalp_mode: bool = False,
    *,
    risk_usdt: float | None = None,
    risk_usdt_max: float | None = None,
    available_usdt: float | None = None,
    min_leverage_cap: int | None = None,
    max_leverage_cap: int | None = None,
    max_notional_cap: float | None = None,
) -> CryptoFuturesPlan:
    """Size a crypto futures trade with strict SL and auto leverage."""
    direction = direction.upper()
    if direction not in ("LONG", "SHORT"):
        direction = "LONG" if direction == "BULLISH" else "SHORT"

    tier = classify_tier(symbol)
    pair = symbol if symbol.endswith("USDT") else f"{symbol}USDT"

    if not stop_loss or stop_loss <= 0:
        return _failed_plan(pair, direction, entry, "NO_TRADE — stop_loss_price missing")

    sl_ok, sl_reason = validate_stop_distance(entry, stop_loss, tier, scalp_mode=scalp_mode)
    if not sl_ok:
        return _failed_plan(pair, direction, entry, f"NO_TRADE — {sl_reason}")

    stop_dist_pct = abs(entry - stop_loss) / entry * 100
    leverage = suggest_leverage(
        pair, atr_pct, stop_dist_pct, tier, entry, stop_loss, direction,
        min_leverage_cap=min_leverage_cap,
        max_leverage_cap=max_leverage_cap,
    )
    max_lev = TIER_MAX_LEV.get(tier, 5)

    if risk_usdt is None:
        risk_usdt = capital_usdt * (risk_percent / 100.0)
    if risk_usdt_max is not None:
        risk_usdt = min(risk_usdt, risk_usdt_max)
    stop_frac = abs(entry - stop_loss) / entry
    if stop_frac <= 0:
        return _failed_plan(pair, direction, entry, "Invalid stop distance")

    notional_at_risk = risk_usdt / stop_frac
    margin_required = notional_at_risk / leverage
    max_margin = capital_usdt * (max_deploy_pct / 100.0)
    if available_usdt is not None:
        max_margin = min(max_margin, available_usdt * (max_deploy_pct / 100.0))

    if margin_required > max_margin:
        margin_required = max_margin
        notional_usdt = margin_required * leverage
        max_loss_usdt = notional_usdt * stop_frac
        quantity = notional_usdt / entry if entry > 0 else 0
    else:
        quantity = notional_at_risk / entry if entry > 0 else 0
        notional_usdt = margin_required * leverage
        max_loss_usdt = notional_usdt * stop_frac if entry > 0 else 0

    if risk_usdt_max is not None and max_loss_usdt > risk_usdt_max * 1.02 and entry > 0:
        max_loss_usdt = risk_usdt_max
        notional_usdt = max_loss_usdt / stop_frac
        margin_required = notional_usdt / leverage
        quantity = notional_usdt / entry

    if max_notional_cap is not None and notional_usdt > max_notional_cap and entry > 0:
        notional_usdt = max_notional_cap
        margin_required = notional_usdt / leverage
        max_loss_usdt = notional_usdt * stop_frac
        quantity = notional_usdt / entry

    liq = liquidation_price(entry, leverage, direction)
    liq_dist = abs(entry - liq)
    stop_dist = abs(entry - stop_loss)
    target_dist = abs(target_1 - entry)
    target_profit_usdt = notional_usdt * (target_dist / entry) if entry > 0 else 0
    liq_buffer = (liq_dist / stop_dist * 100) if stop_dist > 0 else 0

    rr = target_dist / stop_dist if stop_dist > 0 else 0

    sl_pct = -stop_dist_pct if direction == "LONG" else stop_dist_pct
    t1_pct = ((target_1 - entry) / entry * 100) if direction == "LONG" else ((entry - target_1) / entry * 100)
    t2_pct = ((target_2 - entry) / entry * 100) if direction == "LONG" else ((entry - target_2) / entry * 100)

    sl_word = "below" if direction == "LONG" else "above"
    strict_sl = (
        f"Exit immediately if price touches or closes {sl_word} {stop_loss:.8g} "
        f"— no averaging, no moving SL wider"
    )

    dir_label = "LONG" if direction == "LONG" else "SHORT"
    trade_plan = (
        f"{dir_label} {pair.replace('USDT', '')} · Entry {entry:.8g} · "
        f"Target {target_1:.8g} · STRICT SL {stop_loss:.8g} · {leverage}x"
    )

    loss_cap = risk_usdt_max if risk_usdt_max is not None else risk_usdt
    can_afford = (
        margin_required <= max_margin * 1.01
        and max_loss_usdt <= loss_cap * 1.05
        and margin_required > 0
        and quantity > 0
        and not liquidation_too_close(entry, stop_loss, leverage, direction)
    )

    reason = "OK" if can_afford else "Cannot afford position within risk budget"
    if liquidation_too_close(entry, stop_loss, leverage, direction):
        can_afford = False
        reason = "Liquidation too close to stop (< 2× stop distance)"

    return CryptoFuturesPlan(
        symbol=pair,
        direction=direction,
        leverage=leverage,
        max_leverage=max_lev,
        quantity=quantity,
        entry_price=entry,
        stop_loss_price=stop_loss,
        target_1_price=target_1,
        target_2_price=target_2,
        liquidation_price=liq,
        margin_usdt=margin_required,
        notional_usdt=notional_usdt,
        max_loss_usdt=max_loss_usdt,
        target_profit_usdt=target_profit_usdt,
        risk_percent=risk_percent,
        can_afford=can_afford,
        strict_sl_rule=strict_sl,
        trade_plan=trade_plan,
        reason=reason,
        stop_loss_pct=sl_pct,
        target_1_pct=t1_pct,
        target_2_pct=t2_pct,
        risk_reward=rr,
        liquidation_buffer_pct=liq_buffer,
        tier=tier,
        sl_basis=sl_basis,
    )


def _failed_plan(symbol: str, direction: str, entry: float, reason: str) -> CryptoFuturesPlan:
    return CryptoFuturesPlan(
        symbol=symbol,
        direction=direction,
        leverage=1,
        max_leverage=1,
        quantity=0,
        entry_price=entry,
        stop_loss_price=0,
        target_1_price=0,
        target_2_price=0,
        liquidation_price=0,
        margin_usdt=0,
        notional_usdt=0,
        max_loss_usdt=0,
        target_profit_usdt=0,
        risk_percent=0,
        can_afford=False,
        strict_sl_rule="",
        trade_plan="",
        reason=reason,
    )
