from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from kaburadar3.market_data.prices import (
    FetchSpec,
    _fetch_price_data,
    calendar_gap_days_needing_fetch,
    menu_key_for_gap_days,
    resolve_auto_spec,
)


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


def test_menu_key_for_gap_days() -> None:
    assert menu_key_for_gap_days(0) == "1"
    assert menu_key_for_gap_days(1) == "1"
    assert menu_key_for_gap_days(5) == "6"
    assert menu_key_for_gap_days(8) == "2"
    assert menu_key_for_gap_days(20) == "3"


def test_calendar_gap_no_missing() -> None:
    today = date(2026, 9, 25)
    existing = {today}
    assert calendar_gap_days_needing_fetch(existing, today=today, lookback_days=31) == 0


def test_calendar_gap_stale_latest() -> None:
    today = date(2026, 9, 25)
    existing = {date(2026, 9, 3)}
    gap = calendar_gap_days_needing_fetch(existing, today=today, lookback_days=31)
    assert gap == (today - date(2026, 9, 3)).days
    assert menu_key_for_gap_days(gap) == "3"


def test_calendar_gap_one_day_behind() -> None:
    today = date(2026, 9, 25)
    existing = {date(2026, 9, 24)}
    assert calendar_gap_days_needing_fetch(existing, today=today) == 1
    assert menu_key_for_gap_days(1) == "1"


def test_resolve_auto_spec_missing_db(tmp_path) -> None:
    spec = resolve_auto_spec(tmp_path / "missing.db", today=date(2026, 9, 25))
    assert spec.label == "30日"
