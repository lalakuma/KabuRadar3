"""特定年のバックテスト深掘り（月別・地合い・損切りクラスター）."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from kaburadar3.analytics.backtest_deep import (
    _aggregate_group,
    _hold_bucket,
    _parse_date,
    _regime_label,
    enrich_trades,
    load_code_metadata,
    load_market_closes,
    market_return_at,
)
from kaburadar3.analytics.backtest_report import _calc_pf


def _month_key(entry: str) -> str:
    return entry[:7]


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"trades": 0}
    wins = [r for r in rows if int(r["gain"]) > 0]
    losses = [r for r in rows if int(r["gain"]) < 0]
    stops = [r for r in rows if r.get("exit_reason") == "損切り"]
    rsi = [r for r in rows if r.get("exit_reason") == "RSI60"]
    rets = [r["market_return_20d"] for r in rows if r.get("market_return_20d") is not None]
    return {
        "trades": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(rows) * 100, 1),
        "pf": _calc_pf(wins, losses),
        "total_gain": sum(int(r["gain"]) for r in rows),
        "stop_loss_count": len(stops),
        "stop_loss_rate_pct": round(len(stops) / len(rows) * 100, 1),
        "stop_loss_gain": sum(int(r["gain"]) for r in stops),
        "rsi60_count": len(rsi),
        "rsi60_gain": sum(int(r["gain"]) for r in rsi),
        "avg_market_return_20d": round(sum(rets) / len(rets), 2) if rets else None,
        "avg_hold_days": round(sum(int(r.get("hold_days", 0)) for r in rows) / len(rows), 1),
    }


def _market_month_avg(closes: dict[date, float], month: str) -> float | None:
    """月の各営業日における20日リターンの平均."""
    y, m = int(month[:4]), int(month[5:7])
    vals: list[float] = []
    for d, _ in sorted(closes.items()):
        if d.year == y and d.month == m:
            r = market_return_at(closes, d)
            if r is not None:
                vals.append(r)
    return round(sum(vals) / len(vals), 2) if vals else None


def analyze_year(
    enriched: list[dict[str, Any]],
    *,
    year: int,
    market_closes: dict[date, float],
    compare_years: list[int] | None = None,
) -> dict[str, Any]:
    year_rows = [t for t in enriched if t["entry_year"] == year]
    compare_years = compare_years or [year - 1, year + 1]

    by_month: dict[str, list] = defaultdict(list)
    for t in year_rows:
        by_month[_month_key(t["entry"])].append(t)

    months = []
    for month in sorted(by_month):
        block = _stats(by_month[month])
        block["month"] = month
        block["market_avg_20d"] = _market_month_avg(market_closes, month)
        months.append(block)

    by_regime = _aggregate_group(year_rows, "market_regime")
    stop_rows = [t for t in year_rows if t.get("exit_reason") == "損切り"]
    stop_by_hold = _aggregate_group(stop_rows, "hold_bucket")
    stop_by_month = {m["month"]: m["stop_loss_rate_pct"] for m in months}

    # 銘柄別損切り
    by_code: dict[str, list] = defaultdict(list)
    for t in stop_rows:
        by_code[t["code"]].append(t)
    code_stops = []
    for code, rows in by_code.items():
        code_stops.append(
            {
                "code": code,
                "name": rows[0].get("name", ""),
                "stop_loss_count": len(rows),
                "total_gain": sum(int(r["gain"]) for r in rows),
            }
        )
    code_stops.sort(key=lambda x: (x["stop_loss_count"], x["total_gain"]))

    worst_trades = sorted(year_rows, key=lambda x: int(x["gain"]))[:20]
    worst_stops = sorted(stop_rows, key=lambda x: int(x["gain"]))[:15]

    # 四半期
    def qkey(t: dict) -> str:
        m = int(t["entry"][5:7])
        return f"{year}-Q{(m - 1) // 3 + 1}"

    by_q: dict[str, list] = defaultdict(list)
    for t in year_rows:
        by_q[qkey(t)].append(t)
    quarters = [{"key": k, **_stats(v)} for k, v in sorted(by_q.items())]

    # 年比較
    year_compare = []
    for y in sorted(set([year, *compare_years])):
        rows = [t for t in enriched if t["entry_year"] == y]
        if not rows:
            continue
        year_compare.append({"year": y, **_stats(rows)})

    # 高損切率月（20件以上）
    bad_months = [m for m in months if m["trades"] >= 20 and m.get("stop_loss_rate_pct", 0) >= 45]

    # COVID急落窗口 2020-02 ~ 2020-04
    covid_window = [
        t
        for t in enriched
        if t["entry"] >= f"{year}-02-01" and t["entry"] <= f"{year}-04-30" and t["entry_year"] == year
    ]

    return {
        "year": year,
        "summary": _stats(year_rows),
        "by_month": months,
        "by_quarter": quarters,
        "by_market_regime": by_regime,
        "stop_loss_by_hold": stop_by_hold,
        "top_stop_symbols": code_stops[:15],
        "worst_trades": [
            {
                "code": t["code"],
                "name": t.get("name", ""),
                "entry": t["entry"],
                "exit": t["exit"],
                "gain": t["gain"],
                "exit_reason": t.get("exit_reason"),
                "hold_days": t.get("hold_days"),
                "market_regime": t.get("market_regime"),
                "market_return_20d": t.get("market_return_20d"),
            }
            for t in worst_trades
        ],
        "worst_stop_trades": [
            {
                "code": t["code"],
                "name": t.get("name", ""),
                "entry": t["entry"],
                "exit": t["exit"],
                "gain": t["gain"],
                "hold_days": t.get("hold_days"),
                "market_regime": t.get("market_regime"),
            }
            for t in worst_stops
        ],
        "year_compare": year_compare,
        "high_stop_rate_months": bad_months,
        "covid_window_feb_apr": _stats(covid_window),
        "stop_loss_rate_by_month": stop_by_month,
    }


def build_year_breakdown(
    trades: list[dict[str, Any]],
    *,
    year: int,
    metadata: dict[str, dict[str, str]],
    market_closes: dict[date, float],
    compare_years: list[int] | None = None,
) -> dict[str, Any]:
    enriched = enrich_trades(trades, metadata, market_closes)
    return analyze_year(enriched, year=year, market_closes=market_closes, compare_years=compare_years)
