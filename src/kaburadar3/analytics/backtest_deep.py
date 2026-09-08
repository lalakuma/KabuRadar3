"""バックテスト深掘り分析（損切り・年次悪化・地合い・業種）."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from statistics import median
from typing import Any

from kaburadar3.analytics.backtest_report import _calc_pf

MARKET_PROXY_CODE = "1306"
MARKET_LOOKBACK_DAYS = 20


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def load_code_metadata(cursor) -> dict[str, dict[str, str]]:
    cursor.execute('SELECT Code, Name, Sangyou FROM tbl_codelist')
    out: dict[str, dict[str, str]] = {}
    for code, name, sector in cursor.fetchall():
        out[str(code)] = {
            "name": str(name or ""),
            "sector": str(sector or "不明"),
        }
    return out


def load_market_closes(cursor, code: str = MARKET_PROXY_CODE) -> dict[date, float]:
    cursor.execute(f'SELECT datetime, close FROM "tbl_{code}" ORDER BY datetime')
    out: dict[date, float] = {}
    for dt_raw, close in cursor.fetchall():
        if close is None:
            continue
        out[_parse_date(str(dt_raw))] = float(close)
    return out


def market_return_at(closes: dict[date, float], on: date, lookback: int = MARKET_LOOKBACK_DAYS) -> float | None:
    if on not in closes:
        return None
    start = on - timedelta(days=lookback * 2)
    hist = [(d, closes[d]) for d in sorted(closes) if start <= d <= on]
    if len(hist) < 2:
        return None
    recent = hist[-lookback:] if len(hist) >= lookback else hist
    if len(recent) < 2:
        return None
    first = recent[0][1]
    last = recent[-1][1]
    if not first:
        return None
    return (last - first) / first * 100.0


def _regime_label(ret: float | None) -> str:
    if ret is None:
        return "地合い不明"
    if ret >= 3.0:
        return "上昇地合い(+3%〜)"
    if ret <= -3.0:
        return "下落地合い(〜-3%)"
    return "横ばい地合い"


def _hold_bucket(days: int) -> str:
    if days <= 1:
        return "1日"
    if days == 2:
        return "2日"
    if days <= 5:
        return "3-5日"
    if days <= 10:
        return "6-10日"
    return "11日以上"


def _aggregate_group(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or "不明")].append(row)
    out: list[dict[str, Any]] = []
    for k in sorted(groups):
        g = groups[k]
        wins = [x for x in g if int(x["gain"]) > 0]
        losses = [x for x in g if int(x["gain"]) < 0]
        stop = [x for x in g if x.get("exit_reason") == "損切り"]
        out.append(
            {
                "key": k,
                "trades": len(g),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(g) * 100, 1) if g else None,
                "pf": _calc_pf(wins, losses),
                "total_gain": sum(int(x["gain"]) for x in g),
                "stop_loss_count": len(stop),
                "stop_loss_rate_pct": round(len(stop) / len(g) * 100, 1) if g else None,
                "avg_gain": round(sum(int(x["gain"]) for x in g) / len(g), 1) if g else None,
            }
        )
    out.sort(key=lambda x: x["total_gain"])
    return out


def enrich_trades(
    trades: list[dict[str, Any]],
    metadata: dict[str, dict[str, str]],
    market_closes: dict[date, float],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for t in trades:
        if not t.get("closed"):
            continue
        code = str(t["code"])
        entry = _parse_date(t["entry"])
        meta = metadata.get(code, {})
        mret = market_return_at(market_closes, entry)
        row = dict(t)
        row["entry_year"] = entry.year
        row["entry_month"] = entry.isoformat()[:7]
        row["name"] = meta.get("name", "")
        row["sector"] = meta.get("sector", "不明")
        row["hold_bucket"] = _hold_bucket(int(t.get("hold_days", 0)))
        row["market_return_20d"] = round(mret, 2) if mret is not None else None
        row["market_regime"] = _regime_label(mret)
        enriched.append(row)
    return enriched


def analyze_stop_loss_vs_rsi60(enriched: list[dict[str, Any]]) -> dict[str, Any]:
    closed = enriched
    stops = [t for t in closed if t.get("exit_reason") == "損切り"]
    rsi60 = [t for t in closed if t.get("exit_reason") == "RSI60"]
    others = [t for t in closed if t.get("exit_reason") not in ("損切り", "RSI60")]

    def _stats(rows: list[dict]) -> dict[str, Any]:
        if not rows:
            return {"count": 0}
        gains = [int(r["gain"]) for r in rows]
        holds = [int(r["hold_days"]) for r in rows]
        return {
            "count": len(rows),
            "total_gain": sum(gains),
            "avg_gain": round(sum(gains) / len(gains), 1),
            "median_gain": float(median(gains)),
            "avg_hold_days": round(sum(holds) / len(holds), 1),
            "median_hold_days": float(median(holds)),
        }

    by_hold_stop = _aggregate_group(stops, "hold_bucket")
    by_regime_all = _aggregate_group(closed, "market_regime")
    by_regime_stop = _aggregate_group(stops, "market_regime")
    by_sector_stop = _aggregate_group(stops, "sector")
    by_sector_all = _aggregate_group(closed, "sector")

    sector_stop_rate: list[dict[str, Any]] = []
    all_by_sector = {r["key"]: r for r in by_sector_all}
    for row in by_sector_stop:
        total = all_by_sector.get(row["key"], {}).get("trades", 0)
        if total < 5:
            continue
        sector_stop_rate.append(
            {
                "sector": row["key"],
                "trades": total,
                "stop_loss_count": row["stop_loss_count"],
                "stop_loss_rate_pct": round(row["stop_loss_count"] / total * 100, 1),
                "stop_loss_gain": row["total_gain"],
                "all_gain": all_by_sector[row["key"]]["total_gain"],
            }
        )
    sector_stop_rate.sort(key=lambda x: x["stop_loss_rate_pct"], reverse=True)

    by_code: dict[str, list] = defaultdict(list)
    for t in stops:
        by_code[t["code"]].append(t)
    repeat_stop = []
    for code, rows in by_code.items():
        if len(rows) < 2:
            continue
        repeat_stop.append(
            {
                "code": code,
                "name": rows[0].get("name", ""),
                "stop_loss_count": len(rows),
                "total_gain": sum(int(r["gain"]) for r in rows),
                "avg_hold_days": round(sum(int(r["hold_days"]) for r in rows) / len(rows), 1),
            }
        )
    repeat_stop.sort(key=lambda x: (x["stop_loss_count"], x["total_gain"]))

    worst_stops = sorted(stops, key=lambda x: int(x["gain"]))[:15]

    by_month_stop: dict[str, int] = Counter(t["entry_month"] for t in stops)
    by_month_all: dict[str, int] = Counter(t["entry_month"] for t in closed)
    month_stop_rate = []
    for month in sorted(by_month_all):
        total = by_month_all[month]
        sc = by_month_stop.get(month, 0)
        month_stop_rate.append(
            {
                "month": month,
                "trades": total,
                "stop_loss_count": sc,
                "stop_loss_rate_pct": round(sc / total * 100, 1) if total else 0,
            }
        )

    return {
        "summary": {
            "stop_loss": _stats(stops),
            "rsi60": _stats(rsi60),
            "other_exits": _stats(others),
            "stop_loss_share_pct": round(len(stops) / len(closed) * 100, 1) if closed else 0,
        },
        "stop_by_hold_days": by_hold_stop,
        "stop_by_market_regime": by_regime_stop,
        "all_by_market_regime": by_regime_all,
        "sector_high_stop_rate": sector_stop_rate[:12],
        "sector_worst_stop_gain": sorted(by_sector_stop, key=lambda x: x["total_gain"])[:10],
        "repeat_stop_loss_symbols": repeat_stop[:15],
        "worst_stop_trades": [
            {
                "code": t["code"],
                "name": t.get("name", ""),
                "entry": t["entry"],
                "exit": t["exit"],
                "gain": t["gain"],
                "hold_days": t["hold_days"],
                "sector": t.get("sector"),
                "market_regime": t.get("market_regime"),
            }
            for t in worst_stops
        ],
        "stop_loss_rate_by_month": month_stop_rate,
    }


def analyze_year_deterioration(enriched: list[dict[str, Any]]) -> dict[str, Any]:
    by_year: dict[int, list] = defaultdict(list)
    for t in enriched:
        by_year[int(t["entry_year"])].append(t)

    year_rows = []
    for year in sorted(by_year):
        g = by_year[year]
        wins = [x for x in g if int(x["gain"]) > 0]
        losses = [x for x in g if int(x["gain"]) < 0]
        stops = [x for x in g if x.get("exit_reason") == "損切り"]
        rsi = [x for x in g if x.get("exit_reason") == "RSI60"]
        year_rows.append(
            {
                "year": year,
                "trades": len(g),
                "win_rate": round(len(wins) / len(g) * 100, 1),
                "pf": _calc_pf(wins, losses),
                "total_gain": sum(int(x["gain"]) for x in g),
                "stop_loss_count": len(stops),
                "stop_loss_rate_pct": round(len(stops) / len(g) * 100, 1),
                "stop_loss_gain": sum(int(x["gain"]) for x in stops),
                "rsi60_count": len(rsi),
                "rsi60_gain": sum(int(x["gain"]) for x in rsi),
                "avg_loss": round(sum(int(x["gain"]) for x in losses) / len(losses), 1) if losses else None,
                "avg_win": round(sum(int(x["gain"]) for x in wins) / len(wins), 1) if wins else None,
            }
        )

    y2025 = [t for t in enriched if t["entry_year"] == 2025]
    y2024 = [t for t in enriched if t["entry_year"] == 2024]
    feb2025 = [t for t in y2025 if t["entry_month"] == "2025-02"]
    jan2025 = [t for t in y2025 if t["entry_month"] == "2025-01"]

    def _month_block(rows: list[dict], label: str) -> dict[str, Any]:
        wins = [x for x in rows if int(x["gain"]) > 0]
        losses = [x for x in rows if int(x["gain"]) < 0]
        stops = [x for x in rows if x.get("exit_reason") == "損切り"]
        return {
            "label": label,
            "trades": len(rows),
            "win_rate": round(len(wins) / len(rows) * 100, 1) if rows else None,
            "pf": _calc_pf(wins, losses),
            "total_gain": sum(int(x["gain"]) for x in rows),
            "stop_loss_count": len(stops),
            "stop_loss_rate_pct": round(len(stops) / len(rows) * 100, 1) if rows else None,
            "stop_loss_gain": sum(int(x["gain"]) for x in stops),
            "avg_market_return_20d": round(
                sum(r["market_return_20d"] for r in rows if r.get("market_return_20d") is not None)
                / max(1, sum(1 for r in rows if r.get("market_return_20d") is not None)),
                2,
            )
            if any(r.get("market_return_20d") is not None for r in rows)
            else None,
        }

    feb_worst = sorted(feb2025, key=lambda x: int(x["gain"]))[:12]
    y2025_stops = [t for t in y2025 if t.get("exit_reason") == "損切り"]
    y2024_stops = [t for t in y2024 if t.get("exit_reason") == "損切り"]

    return {
        "by_year": year_rows,
        "2025_months": [
            _month_block(jan2025, "2025-01"),
            _month_block(feb2025, "2025-02"),
            _month_block([t for t in y2025 if t["entry_month"] == "2025-03"], "2025-03"),
        ],
        "2025_vs_2024": {
            "2024": _month_block(y2024, "2024年全体"),
            "2025": _month_block(y2025, "2025年(〜3月)"),
            "stop_loss_avg_gain_2024": round(sum(int(x["gain"]) for x in y2024_stops) / len(y2024_stops), 1)
            if y2024_stops
            else None,
            "stop_loss_avg_gain_2025": round(sum(int(x["gain"]) for x in y2025_stops) / len(y2025_stops), 1)
            if y2025_stops
            else None,
        },
        "2025_02_worst_trades": [
            {
                "code": t["code"],
                "name": t.get("name", ""),
                "entry": t["entry"],
                "exit": t["exit"],
                "gain": t["gain"],
                "exit_reason": t.get("exit_reason"),
                "hold_days": t["hold_days"],
                "sector": t.get("sector"),
                "market_regime": t.get("market_regime"),
            }
            for t in feb_worst
        ],
        "bad_months_vs_market": [
            _month_block([t for t in enriched if t["entry_month"] == m], m)
            for m in ("2023-09", "2024-04", "2024-07", "2025-02")
        ],
    }


def build_deep_report(
    trades: list[dict[str, Any]],
    *,
    metadata: dict[str, dict[str, str]],
    market_closes: dict[date, float],
) -> dict[str, Any]:
    enriched = enrich_trades(trades, metadata, market_closes)
    return {
        "trade_count_closed": len(enriched),
        "stop_loss_analysis": analyze_stop_loss_vs_rsi60(enriched),
        "year_deterioration": analyze_year_deterioration(enriched),
    }
