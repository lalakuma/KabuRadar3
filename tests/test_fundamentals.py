from __future__ import annotations

import sys

from kaburadar3.market_data.fundamentals import (
    _parse_valuation_from_info,
    fetch_earnings_info,
    fetch_fundamentals_snapshot,
)


def _patch_yfinance(monkeypatch, info: dict) -> None:
    class FakeTicker:
        def __init__(self, symbol: str):
            self.info = info

    monkeypatch.setitem(sys.modules, "yfinance", type("yf", (), {"Ticker": FakeTicker})())


def test_fetch_fundamentals_snapshot_parses_all_sections(monkeypatch) -> None:
    _patch_yfinance(
        monkeypatch,
        {
            "dividendRate": 80,
            "dividendYield": 0.029,
            "exDividendDate": 1803686400,
            "payoutRatio": 0.401,
            "earningsTimestampStart": 1791354600,
            "nextFiscalYearEnd": 1803772800,
            "isEarningsDateEstimate": False,
            "sectorDisp": "Consumer Cyclical",
            "industryDisp": "Apparel Retail",
            "trailingPE": 18.4,
            "forwardPE": 16.2,
            "priceToBook": 2.1,
            "marketCap": 350_000_000_000,
            "currentPrice": 2690,
            "targetMeanPrice": 3100,
            "revenueGrowth": 0.059,
            "earningsGrowth": 0.104,
            "profitMargins": 0.122,
            "returnOnEquity": 0.145,
            "debtToEquity": 42.5,
        },
    )
    out = fetch_fundamentals_snapshot("2670")
    assert out["dividend"]["annual_yen"] == 80
    assert out["earnings"]["fiscal_month"] == 2
    assert out["valuation"]["per"] == 18.4
    assert out["valuation"]["market_cap_oku"] == 3500
    assert out["valuation"]["target_upside_pct"] == 15.2


def test_fetch_earnings_info_uses_snapshot(monkeypatch) -> None:
    _patch_yfinance(
        monkeypatch,
        {
            "earningsTimestampStart": 1791354600,
            "nextFiscalYearEnd": 1803772800,
        },
    )
    out = fetch_earnings_info("2670")
    assert out["announcement_date"] == "2026-10-07"
    assert out["fiscal_month"] == 2


def test_parse_valuation_from_info_empty() -> None:
    assert _parse_valuation_from_info({}) == {}


def test_fetch_earnings_info_empty_on_failure(monkeypatch) -> None:
    class BrokenTicker:
        def __init__(self, symbol: str):
            raise RuntimeError("network")

    monkeypatch.setitem(sys.modules, "yfinance", type("yf", (), {"Ticker": BrokenTicker})())
    assert fetch_fundamentals_snapshot("9999") == {}
