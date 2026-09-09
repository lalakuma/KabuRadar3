from __future__ import annotations

from kaburadar3.analytics.backtest_year_breakdown import analyze_year


def test_analyze_year_monthly() -> None:
    enriched = [
        {
            "code": "1000",
            "name": "A",
            "entry": "2020-01-05",
            "exit": "2020-01-08",
            "entry_year": 2020,
            "entry_month": "2020-01",
            "gain": 5000,
            "hold_days": 3,
            "closed": True,
            "exit_reason": "RSI60",
            "market_regime": "横ばい地合い",
            "market_return_20d": 0.5,
            "hold_bucket": "3-5日",
            "sector": "不明",
        },
        {
            "code": "2000",
            "name": "B",
            "entry": "2020-02-10",
            "exit": "2020-02-12",
            "entry_year": 2020,
            "entry_month": "2020-02",
            "gain": -3000,
            "hold_days": 2,
            "closed": True,
            "exit_reason": "損切り",
            "market_regime": "下落地合い(〜-3%)",
            "market_return_20d": -5.0,
            "hold_bucket": "2日",
            "sector": "不明",
        },
    ]
    report = analyze_year(enriched, year=2020, market_closes={})
    assert report["summary"]["trades"] == 2
    assert len(report["by_month"]) == 2
    assert report["by_month"][1]["month"] == "2020-02"
