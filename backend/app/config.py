from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "*"

    # Quality signals — 10/day · BTC ETH Gold + movers · paper $100 wallet
    crypto_capital_inr: float = 8300.0  # ~100 USDT reference
    paper_wallet_usdt: float = 100.0
    crypto_paper_trading: bool = True
    risk_per_trade_usdt: float = 1.00  # ~1% of $100 paper wallet
    risk_per_trade_usdt_max: float = 1.20
    scalp_rr_min: float = 1.5
    scalp_rr_ratio: float = 2.0
    take_profit_usdt: float = 1.50
    take_profit_usdt_min: float = 1.20
    take_profit_usdt_max: float = 2.00
    min_win_close_usdt: float = 0.80
    binance_taker_fee_pct: float = 0.04
    slippage_pct: float = 0.10
    fee_buffer_usdt: float = 0.01
    max_notional_usdt_small_wallet: float = 200.0
    small_wallet_threshold_usdt: float = 150.0
    bracket_min_distance_pct: float = 0.15
    min_net_profit_to_fee_ratio: float = 2.0
    max_deploy_pct: float = 25.0
    usdt_to_inr: float = 83.0
    trading_style: str = "quality"
    min_rr_for_take: float = 2.0
    normal_min_rr: float = 2.0
    leverage_min: int = 10
    leverage_max: int = 15
    leverage_hq_min: int = 12
    leverage_hq_max: int = 20
    high_quality_min_confidence: int = 85
    elite_min_confidence: int = 90
    backtest_min_win_rate: float = 50.0
    backtest_min_samples: int = 3
    backtest_lookback_bars: int = 80
    core_scan_pairs: str = "BTCUSDT,PAXGUSDT"
    client_data_secret: str = ""

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

    # Signal limits — BTC/Gold focus, up to 10/day
    max_take_signals_per_day: int = 10
    max_high_priority_signals_per_day: int = 10
    max_signals_per_scan: int = 3
    high_priority_min_confidence: int = 85
    high_priority_min_rr: float = 1.5
    history_retention_days: int = 1
    top_mover_scan_count: int = 2
    top_mover_scan_min: int = 5
    mover_refresh_hours: int = 3
    mover_levels_refresh_minutes: int = 15
    top_meme_scan_count: int = 7
    scan_24h_movers_only: bool = False
    scalp_min_confidence: int = 78
    live_min_confidence: int = 72
    normal_min_confidence: int = 75
    notify_min_confidence: int = 82
    signal_cooldown_minutes: int = 15
    scalp_holding_minutes: int = 15
    prioritize_meme_coins: bool = False
    mover_min_confidence: int = 78
    meme_min_confidence: int = 80
    mover_min_volume_usdt: float = 1_500_000.0  # include volatile memes like Binance Markets tab
    mover_min_change_pct: float = 2.5  # fast movers only — floor for |24h %|

    # Safety
    crypto_paper_trading: bool = False  # live signals — user chooses which to take
    min_volume_usdt: float = 15_000_000.0
    meme_min_volume_usdt: float = 1_500_000.0
    max_spread_pct: float = 0.30
    max_funding_rate_pct: float = 0.08
    max_funding_extreme_pct: float = 0.10

    # Alpha Engine gates (relaxed for BTC/Gold — still quality-focused)
    alpha_min_confluence_score: int = 2
    alpha_min_confluence_categories: int = 2
    alpha_ranging_min_confluence: int = 3
    alpha_max_correlated_positions: int = 3
    alpha_min_score_100: int = 70
    alpha_min_score_100_core: int = 65
    grade_a_plus_max_leverage: int = 7
    grade_a_max_leverage: int = 5
    grade_b_max_leverage: int = 3
    max_grade_a_plus_per_day: int = 3
    max_grade_a_per_day: int = 5
    max_grade_b_per_day: int = 2
    loss_cooldown_after_sl: int = 2
    loss_cooldown_risk_multiplier: float = 0.5

    # Delta Exchange India — options/GEX (public + optional API key for fills)
    delta_exchange_base_url: str = "https://api.india.delta.exchange"
    delta_api_key: str = ""
    delta_api_secret: str = ""

    # Scanner — every 5 minutes for quality setups
    scan_interval_seconds: int = 300

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
    auto_execute_min_confidence: int = 85
    max_exchange_trades_per_day: int = 10
    max_exchange_open_positions: int = 1
    trading_paused_default: bool = False

    @property
    def core_pairs_list(self) -> list[str]:
        return [p.strip().upper() for p in self.core_scan_pairs.split(",") if p.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
