from __future__ import annotations

from datetime import date

from kaburadar3.analytics.backtest_deep import (
    _regime_label,
    analyze_stop_loss_vs_rsi60,
    build_deep_report,
    enrich_trades,
    market_return_at,
)


def test_regime_label() -> None:
    assert _regime_label(5.0) == "上昇地合い(+3%〜)"
    assert _regime_label(-5.0) == "下落地合い(〜-3%)"
    assert _regime_label(0.0) == "横ばい地合い"
    assert _regime_label(None) == "地合い不明"


def test_market_return_at() -> None:
    closes = {date(2024, 1, d): 100.0 + d for d in range(1, 32)}
    ret = market_return_at(closes, date(2024, 1, 25), lookback=5)
    assert ret is not None
    assert ret > 0


def test_stop_loss_analysis() -> None:
    trades = [
        {
            "code": "1000",
            "entry": "2025-02-01",
            "exit": "2025-02-03",
            "gain": -12000,
            "hold_days": 2,
            "closed": True,
            "exit_reason": "損切り",
        },
        {
            "code": "2000",
            "entry": "2025-02-05",
            "exit": "2025-02-08",
            "gain": 5000,
            "hold_days": 3,
            "closed": True,
            "exit_reason": "RSI60",
        },
    ]
    metadata = {
        "1000": {"name": "A", "sector": "電機"},
        "2000": {"name": "B", "sector": "小売"},
    }
    enriched = enrich_trades(trades, metadata, {})
    report = analyze_stop_loss_vs_rsi60(enriched)
    assert report["summary"]["stop_loss"]["count"] == 1
    assert report["summary"]["rsi60"]["count"] == 1


def test_build_deep_report() -> None:
    trades = [
        {
            "code": "1000",
            "entry": "2024-01-01",
            "exit": "2024-01-04",
            "gain": -3000,
            "hold_days": 3,
            "closed": True,
            "exit_reason": "損切り",
        }
    ]
    report = build_deep_report(trades, metadata={"1000": {"name": "X", "sector": "銀行"}}, market_closes={})
    assert report["trade_count_closed"] == 1
    assert "stop_loss_analysis" in report
