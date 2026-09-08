from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from kaburadar3.market_data.prices import FetchSpec, _fetch_price_data


def test_fetch_price_data_uses_auto_adjust() -> None:
    spec = FetchSpec("5日", "day", 5)
    index = pd.DatetimeIndex(["2026-01-01"], name="datetime")
    frame = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [1000],
        },
        index=index,
    )
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = frame

    with patch("kaburadar3.market_data.prices.yf.Ticker", return_value=mock_ticker):
        out = _fetch_price_data("7203", spec)

    mock_ticker.history.assert_called_once_with(period="5d", interval="1d", auto_adjust=True)
    assert not out.empty
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]


def test_fetch_price_data_10y_period() -> None:
    spec = FetchSpec("10年", "year", 10)
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()

    with patch("kaburadar3.market_data.prices.yf.Ticker", return_value=mock_ticker):
        _fetch_price_data("7203", spec)

    mock_ticker.history.assert_called_once_with(period="10y", interval="1d", auto_adjust=True)
