from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "*"

    # Capital & risk — scalp 1:1 / 1:2 off SL distance (fees + slippage buffered)
    crypto_capital_inr: float = 20000.0
    risk_per_trade_usdt: float = 0.30  # ~₹25 at SL
    risk_per_trade_usdt_max: float = 0.36  # ~₹30 at SL
    scalp_rr_min: float = 1.0  # 1:1 for standard signals
    scalp_rr_ratio: float = 2.0  # 1:2 for HQ signals (80%+ confidence)
    take_profit_usdt: float = 0.48  # reference ~₹40 net at 1:2
    take_profit_usdt_min: float = 0.24  # ~₹20 at 1:1
    take_profit_usdt_max: float = 0.60  # ~₹50 at 1:2
    min_win_close_usdt: float = 0.18  # bank small green on timeout (~₹15)
    binance_taker_fee_pct: float = 0.04
    slippage_pct: float = 0.12  # realistic entry slippage % on notional
    fee_buffer_usdt: float = 0.01
    max_notional_usdt_small_wallet: float = 42.0  # cap ~$40 pos on ~$35 wallet
    small_wallet_threshold_usdt: float = 60.0
    bracket_min_distance_pct: float = 0.20  # SL/TP must be 0.2%+ from fill
    min_net_profit_to_fee_ratio: float = 1.2  # used at execute time only
    max_deploy_pct: float = 40.0
    usdt_to_inr: float = 83.0
    trading_style: str = "scalp"
    min_rr_for_take: float = 1.0  # HQ notify — matches 1:1 scalp floor
    normal_min_rr: float = 1.0
    leverage_min: int = 15
    leverage_max: int = 20
    leverage_hq_min: int = 20  # confidence >= 80%
    leverage_hq_max: int = 25  # confidence >= 90%
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
    scalp_holding_minutes: int = 3  # in-out within 3 min
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
    max_exchange_trades_per_day: int = 80
    max_exchange_open_positions: int = 1  # one trade at a time on small wallet
    trading_paused_default: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
