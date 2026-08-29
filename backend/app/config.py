from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "*"

    # Micro pure scalp — $0.22 risk, $0.25 profit, high leverage fast in/out
    crypto_capital_inr: float = 20000.0
    risk_per_trade_usdt: float = 0.22  # ~₹18 at SL
    risk_per_trade_usdt_max: float = 0.25  # ~₹21 cap
    scalp_rr_min: float = 1.1  # ~$0.24 on $0.22 risk
    scalp_rr_ratio: float = 1.25  # ~$0.28 HQ
    take_profit_usdt: float = 0.25  # ~₹21
    take_profit_usdt_min: float = 0.22  # ~₹18 min net
    take_profit_usdt_max: float = 0.30  # ~₹25 HQ
    min_win_close_usdt: float = 0.15  # bank ~₹12+ on timeout scalp
    binance_taker_fee_pct: float = 0.04
    slippage_pct: float = 0.10
    fee_buffer_usdt: float = 0.01
    max_notional_usdt_small_wallet: float = 70.0  # tight size — fees stay small
    small_wallet_threshold_usdt: float = 80.0
    bracket_min_distance_pct: float = 0.12
    min_net_profit_to_fee_ratio: float = 1.5
    max_deploy_pct: float = 40.0
    usdt_to_inr: float = 83.0
    trading_style: str = "scalp"
    min_rr_for_take: float = 1.0
    normal_min_rr: float = 0.9
    leverage_min: int = 25
    leverage_max: int = 35
    leverage_hq_min: int = 30
    leverage_hq_max: int = 40
    high_quality_min_confidence: int = 80
    elite_min_confidence: int = 90

    @property
    def risk_per_trade_inr(self) -> float:
        return round(self.risk_per_trade_usdt * self.usdt_to_inr, 0)

    @property
    def take_profit_inr(self) -> float:
        return round(self.take_profit_usdt * self.usdt_to_inr, 0)

    @property
    def scalp_target_inr(self) -> float:
        return self.take_profit_inr

    @property
    def target_profit_inr_min(self) -> float:
        return round(self.take_profit_usdt_min * self.usdt_to_inr, 0)

    @property
    def take_profit_inr_max(self) -> float:
        return round(self.take_profit_usdt_max * self.usdt_to_inr, 0)

    @property
    def min_win_close_inr(self) -> float:
        return round(self.min_win_close_usdt * self.usdt_to_inr, 0)

    @property
    def crypto_capital_usdt(self) -> float:
        return round(self.crypto_capital_inr / self.usdt_to_inr, 2)

    @property
    def risk_percent(self) -> float:
        cap = self.crypto_capital_usdt
        if cap <= 0:
            return 0.0
        return round(self.risk_per_trade_usdt / cap * 100, 2)

    # Database — Neon Postgres (free tier) or local SQLite fallback
    database_url: str = ""
    sqlite_path: str = "./data/cryptoapp.db"

    # Signal limits — high-frequency 1m dip/top scalp on fast movers
    max_take_signals_per_day: int = 200
    max_high_priority_signals_per_day: int = 60
    max_signals_per_scan: int = 30
    high_priority_min_confidence: int = 80
    high_priority_min_rr: float = 1.0
    history_retention_days: int = 7
    top_mover_scan_count: int = 25  # more fast-move coins for 1m scalp
    top_mover_scan_min: int = 15
    mover_refresh_hours: int = 3  # re-fetch 24h % leaders every 3 hours
    mover_levels_refresh_minutes: int = 12  # Entry/SL/TP1 valid ~12m then refresh
    top_meme_scan_count: int = 25  # alias kept for compat
    scan_24h_movers_only: bool = True  # only trade highest 24h move % coins
    scalp_min_confidence: int = 60
    live_min_confidence: int = 48
    normal_min_confidence: int = 48  # more 1m dip/top signals
    notify_min_confidence: int = 70
    signal_cooldown_minutes: int = 1  # fast re-entry for high-frequency scalp
    scalp_holding_minutes: int = 2  # fast in-out within 2 min
    prioritize_meme_coins: bool = True
    mover_min_confidence: int = 48  # top 24h movers
    meme_min_confidence: int = 48
    mover_min_volume_usdt: float = 1_500_000.0  # include volatile memes like Binance Markets tab
    mover_min_change_pct: float = 2.5  # fast movers only — floor for |24h %|

    # Safety
    crypto_paper_trading: bool = False  # live signals — user chooses which to take
    min_volume_usdt: float = 15_000_000.0
    meme_min_volume_usdt: float = 1_500_000.0
    max_spread_pct: float = 0.10
    max_funding_rate_pct: float = 0.08

    # Scanner — every 1 minute for 1m dip/top scalp
    scan_interval_seconds: int = 60

    # Auto-disable setups that keep losing (aggressive)
    setup_disable_min_trades: int = 3
    setup_disable_max_win_rate: float = 38.0

    # Binance market data — Vision for klines/price/depth/ticker (no API key)
    binance_data_base_url: str = "https://data-api.binance.vision"
    binance_futures_base_url: str = "https://fapi.binance.com"
    binance_fstream_ws_url: str = "wss://fstream.binance.com"

    # Binance Futures auto-execution (API keys on server only — never in the app)
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_futures_testnet: bool = False
    auto_execute_trades: bool = False
    auto_execute_min_confidence: int = 72
    max_exchange_trades_per_day: int = 150
    max_exchange_open_positions: int = 1
    trading_paused_default: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
