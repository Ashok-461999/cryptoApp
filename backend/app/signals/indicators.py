"""pandas-ta wrappers — indicators on OHLCV."""

import pandas as pd
import pandas_ta as ta


def ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing columns: {missing}")
    out = df.copy()
    for col in required:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["open", "high", "low", "close"])


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    d = ensure_ohlcv(df)
    return ta.atr(d["high"], d["low"], d["close"], length=length)


def vwap(df: pd.DataFrame) -> pd.Series:
    d = ensure_ohlcv(df)
    return ta.vwap(d["high"], d["low"], d["close"], d["volume"])


def add_standard_indicators(df: pd.DataFrame) -> pd.DataFrame:
    d = ensure_ohlcv(df).copy()
    d["atr_14"] = atr(d, 14)
    d["vwap"] = vwap(d)
    d["vol_sma_20"] = d["volume"].rolling(20, min_periods=5).mean()
    return d


def atr_pct(df: pd.DataFrame) -> float:
    d = add_standard_indicators(df)
    if d.empty:
        return 2.0
    bar = d.iloc[-1]
    close = float(bar["close"])
    atr_val = float(bar["atr_14"]) if not pd.isna(bar["atr_14"]) else close * 0.02
    return (atr_val / close * 100) if close > 0 else 2.0
