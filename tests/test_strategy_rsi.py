from __future__ import annotations

import pandas as pd

from kaburadar3.domain.constants import MODE_BUY, MODE_SELL
from kaburadar3.strategy import rsi


def _sample_ohlc(n: int = 30) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(range(100, 100 + n), dtype=float, index=idx)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000,
        },
        index=idx,
    )


def test_rsi_tradingview_adds_rsi4() -> None:
    df = rsi.rsi_tradingview(_sample_ohlc(), period=4)
    assert "RSI4" in df.columns
    assert df["RSI4"].notna().any()


def test_jdg_rsi_short_returns_int() -> None:
    df = rsi.rsi_tradingview(_sample_ohlc(), period=4)
    sig = rsi.jdg_rsi_short(MODE_BUY, df, srsi_low=30, jdg_rsi4rev=0)
    assert sig in (0, 1)


def test_jdg_rsi_shortkessai_returns_bool() -> None:
    df = rsi.rsi_tradingview(_sample_ohlc(), period=4)
    assert isinstance(rsi.jdg_rsi_shortkessai(MODE_SELL, df, srsi_hi=70, srsi_low=30), bool)
