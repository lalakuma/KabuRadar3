from __future__ import annotations

from kaburadar3.analytics.backtest_report import (
    build_report,
    exit_reason_breakdown,
    infer_exit_reason,
    summarize_window,
)


def test_infer_exit_reason_rsi60() -> None:
    row = {"close": 110, "RSI4": 65}
    assert infer_exit_reason(100, row, 5, stop_pct=3, sell_period=100, rsi_hi=60) == "RSI60"


def test_infer_exit_reason_stop() -> None:
    row = {"close": 96, "RSI4": 20}
    assert infer_exit_reason(100, row, 2, stop_pct=3, sell_period=100, rsi_hi=60) == "損切り"


def test_build_report_aggregates() -> None:
    trades = [
        {
            "code": "1000",
            "entry": "2024-03-01",
            "exit": "2024-03-05",
            "gain": 5000,
            "hold_days": 3,
            "closed": True,
            "exit_reason": "RSI60",
        },
        {
            "code": "2000",
            "entry": "2025-01-10",
            "exit": "2025-01-12",
            "gain": -2000,
            "hold_days": 2,
            "closed": True,
            "exit_reason": "損切り",
        },
    ]
    report = build_report(trades, label="test", past_period_days=1200, symbols_enabled=2, symbols_traded=2)
    assert report["summary"]["closed"] == 2
    assert report["summary"]["total_gain"] == 3000
    assert len(report["by_year"]) == 2
    reasons = {row["reason"] for row in exit_reason_breakdown(trades)}
    assert reasons == {"RSI60", "損切り"}


def test_summarize_window_empty() -> None:
    s = summarize_window([], label="empty", past_period_days=100, symbols_enabled=0, symbols_traded=0)
    assert s.entries == 0
    assert s.pf is None
