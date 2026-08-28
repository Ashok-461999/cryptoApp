from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "*"

    # Capital & risk — ₹20,000 INR
    crypto_capital_inr: float = 20000.0
    risk_per_trade_inr: float = 200.0  # fixed ₹200 risk per trade (max loss at SL)
    max_deploy_pct: float = 40.0
    usdt_to_inr: float = 83.0
    trading_style: str = "scalp"
    min_rr_for_take: float = 3.0  # 1:3 — ₹200 risk → ₹600+ scalp win at T1
    normal_min_rr: float = 2.0  # NORMAL tier can show 1:2 setups
    target_profit_inr_min: float = 600.0
    take_profit_inr: float = 600.0  # auto-close WIN when live PnL ≥ ₹600
    scalp_target_inr: float = 600.0  # primary scalp bank target
    leverage_min: int = 25
    leverage_max: int = 40

    @property
    def crypto_capital_usdt(self) -> float:
        return round(self.crypto_capital_inr / self.usdt_to_inr, 2)

    @property
    def risk_percent(self) -> float:
        return round(self.risk_per_trade_inr / self.crypto_capital_inr * 100, 2)

    # Database — Neon Postgres (free tier) or local SQLite fallback
    database_url: str = ""
    sqlite_path: str = "./data/cryptoapp.db"

    # Signal limits — 60–70/day total, 40 highlighted HIGH priority
    max_take_signals_per_day: int = 70
    max_high_priority_signals_per_day: int = 40
    max_signals_per_scan: int = 15
    high_priority_min_confidence: int = 85
    high_priority_min_rr: float = 3.0
    history_retention_days: int = 7
    top_mover_scan_count: int = 15  # top 10–15 Binance 24h % movers (Markets tab)
    top_mover_scan_min: int = 10
    mover_refresh_hours: int = 3  # re-fetch 24h % leaders every 3 hours
    top_meme_scan_count: int = 15  # alias kept for compat
    scan_24h_movers_only: bool = True  # only trade highest 24h move % coins
    scalp_min_confidence: int = 65
    live_min_confidence: int = 50
    normal_min_confidence: int = 50  # emit signals when confidence > 50%
    notify_min_confidence: int = 72
    signal_cooldown_minutes: int = 10
    scalp_holding_minutes: int = 45  # quick scalp — exit if no ₹600 in 45 min
    prioritize_meme_coins: bool = True
    mover_min_confidence: int = 50  # top 24h movers
    meme_min_confidence: int = 50
    min_win_close_inr: float = 600.0  # no WIN below ₹600 (blocks small noise)
    mover_min_volume_usdt: float = 1_500_000.0  # include volatile memes like Binance Markets tab
    mover_min_change_pct: float = 5.0  # floor only — we always take top 10–15 by |24h %|

    # Safety
    crypto_paper_trading: bool = False  # live signals — user chooses which to take
    min_volume_usdt: float = 15_000_000.0
    meme_min_volume_usdt: float = 1_500_000.0
    max_spread_pct: float = 0.10
    max_funding_rate_pct: float = 0.08

    # Scanner — every 2 minutes for scalp on 24h movers
    scan_interval_seconds: int = 120

    # Auto-disable setups that keep losing (aggressive)
    setup_disable_min_trades: int = 3
    setup_disable_max_win_rate: float = 38.0

    # Binance market data — Vision for klines/price/depth/ticker (no API key)
    binance_data_base_url: str = "https://data-api.binance.vision"
    binance_futures_base_url: str = "https://fapi.binance.com"
    binance_fstream_ws_url: str = "wss://fstream.binance.com"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
