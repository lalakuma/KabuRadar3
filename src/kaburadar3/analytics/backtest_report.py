"""バックテスト結果の多面的集計."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any

from kaburadar3.settings import screening as conf

EXIT_LABELS = ("損切り", "RSI60", "100日", "その他")


@dataclass
class WindowSummary:
    label: str
    past_period_days: int
    symbols_enabled: int
    symbols_traded: int
    entries: int
    closed: int
    open_count: int
    wins: int
    losses: int
    win_rate: float | None
    pf: float | None
    total_gain: int
    avg_gain: float | None
    median_gain: float | None
    max_gain: int
    max_loss: int
    avg_win: float | None
    avg_loss: float | None
    avg_hold_days: float | None


def infer_exit_reason(
    buy_price: float,
    exit_row: Any,
    hold_days: int,
    *,
    stop_pct: float,
    sell_period: int,
    rsi_hi: float,
) -> str:
    exit_close = float(exit_row["close"])
    pct = (exit_close - buy_price) / buy_price * 100.0 if buy_price else 0.0
    rsi4 = float(exit_row.get("RSI4", 0) or 0)
    if pct <= -stop_pct + 0.05:
        return "損切り"
    if hold_days >= sell_period:
        return "100日"
    if rsi4 > rsi_hi:
        return "RSI60"
    return "その他"


def row_date(row: Any, idx: object) -> date:
    dt = row.get("Index", row.get("datetime", idx))
    if isinstance(dt, datetime):
        return dt.date()
    if isinstance(dt, date):
        return dt
    return datetime.fromisoformat(str(dt)[:10]).date()


def extract_trades_from_outdf(code: str, outdf: Any) -> list[dict[str, Any]]:
    if outdf is None or getattr(outdf, "empty", True):
        return []
    stop_pct = float(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_STOP_LOSS_PCT, default="3"))
    sell_period = int(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_SELL_PERIOD))
    rsi_hi = float(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_SRSI_HI, default="60"))

    trades: list[dict[str, Any]] = []
    entry_date: date | None = None
    buy_price = 0.0
    hold_days = 0

    for idx, row in outdf.iterrows():
        mark = str(row.get("mark", ""))
        if mark == "新買":
            entry_date = row_date(row, idx)
            buy_price = float(row["close"])
            hold_days = 0
        elif mark == "継続" and entry_date is not None:
            hold_days += 1
        elif mark == "返売" and entry_date is not None:
            hold_days += 1
            gain = int(row.get("buygain", 0) or 0)
            exit_date = row_date(row, idx)
            trades.append(
                {
                    "code": str(code),
                    "entry": entry_date.isoformat(),
                    "exit": exit_date.isoformat(),
                    "buy_price": int(buy_price),
                    "exit_price": int(row.get("close", 0) or 0),
                    "gain": gain,
                    "hold_days": hold_days,
                    "closed": True,
                    "exit_reason": infer_exit_reason(
                        buy_price,
                        row,
                        hold_days,
                        stop_pct=stop_pct,
                        sell_period=sell_period,
                        rsi_hi=rsi_hi,
                    ),
                }
            )
            entry_date = None
            buy_price = 0.0
            hold_days = 0

    if entry_date is not None:
        trades.append(
            {
                "code": str(code),
                "entry": entry_date.isoformat(),
                "exit": None,
                "buy_price": int(buy_price),
                "exit_price": None,
                "gain": 0,
                "hold_days": hold_days,
                "closed": False,
                "exit_reason": None,
            }
        )
    return trades


def _calc_pf(wins: list[dict], losses: list[dict]) -> float | None:
    plus = sum(int(t["gain"]) for t in wins)
    minus = sum(int(t["gain"]) for t in losses)
    if minus:
        return round(plus / abs(minus), 3)
    return round(float(plus), 3) if plus else None


def summarize_window(
    trades: list[dict[str, Any]],
    *,
    label: str,
    past_period_days: int,
    symbols_enabled: int,
    symbols_traded: int,
) -> WindowSummary:
    closed = [t for t in trades if t.get("closed")]
    open_rows = [t for t in trades if not t.get("closed")]
    wins = [t for t in closed if int(t.get("gain", 0)) > 0]
    losses = [t for t in closed if int(t.get("gain", 0)) < 0]
    gains = [int(t["gain"]) for t in closed]
    total = sum(gains)
    wr = len(wins) / len(closed) * 100 if closed else None
    holds = [int(t.get("hold_days", 0)) for t in closed]
    return WindowSummary(
        label=label,
        past_period_days=past_period_days,
        symbols_enabled=symbols_enabled,
        symbols_traded=symbols_traded,
        entries=len(trades),
        closed=len(closed),
        open_count=len(open_rows),
        wins=len(wins),
        losses=len(losses),
        win_rate=round(wr, 2) if wr is not None else None,
        pf=_calc_pf(wins, losses),
        total_gain=total,
        avg_gain=round(total / len(closed), 1) if closed else None,
        median_gain=float(median(gains)) if gains else None,
        max_gain=max(gains) if gains else 0,
        max_loss=min(gains) if gains else 0,
        avg_win=round(sum(int(t["gain"]) for t in wins) / len(wins), 1) if wins else None,
        avg_loss=round(sum(int(t["gain"]) for t in losses) / len(losses), 1) if losses else None,
        avg_hold_days=round(sum(holds) / len(holds), 1) if holds else None,
    )


def bucket_hold_days(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closed = [t for t in trades if t.get("closed")]
    buckets = [
        ("1-5日", lambda d: 1 <= d <= 5),
        ("6-15日", lambda d: 6 <= d <= 15),
        ("16-30日", lambda d: 16 <= d <= 30),
        ("31-60日", lambda d: 31 <= d <= 60),
        ("61-100日", lambda d: 61 <= d <= 100),
    ]
    out: list[dict[str, Any]] = []
    for name, pred in buckets:
        rows = [t for t in closed if pred(int(t.get("hold_days", 0)))]
        if not rows:
            continue
        wins = sum(1 for t in rows if int(t["gain"]) > 0)
        out.append(
            {
                "bucket": name,
                "count": len(rows),
                "win_rate": round(wins / len(rows) * 100, 1),
                "total_gain": sum(int(t["gain"]) for t in rows),
            }
        )
    return out


def aggregate_by_key(trades: list[dict[str, Any]], key_fn) -> list[dict[str, Any]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        if not t.get("closed"):
            continue
        groups[key_fn(t)].append(t)
    rows: list[dict[str, Any]] = []
    for key in sorted(groups):
        g = groups[key]
        wins = [x for x in g if int(x["gain"]) > 0]
        losses = [x for x in g if int(x["gain"]) < 0]
        rows.append(
            {
                "key": key,
                "trades": len(g),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(len(wins) / len(g) * 100, 1) if g else None,
                "pf": _calc_pf(wins, losses),
                "total_gain": sum(int(x["gain"]) for x in g),
            }
        )
    return rows


def top_symbols(trades: list[dict[str, Any]], *, min_trades: int = 2, limit: int = 10) -> dict[str, list]:
    by_code: dict[str, list] = defaultdict(list)
    for t in trades:
        if t.get("closed"):
            by_code[t["code"]].append(t)
    ranked: list[dict[str, Any]] = []
    for code, rows in by_code.items():
        if len(rows) < min_trades:
            continue
        wins = [r for r in rows if int(r["gain"]) > 0]
        losses = [r for r in rows if int(r["gain"]) < 0]
        ranked.append(
            {
                "code": code,
                "trades": len(rows),
                "win_rate": round(len(wins) / len(rows) * 100, 1),
                "pf": _calc_pf(wins, losses),
                "total_gain": sum(int(r["gain"]) for r in rows),
            }
        )
    ranked.sort(key=lambda x: x["total_gain"], reverse=True)
    losers = sorted(ranked, key=lambda x: x["total_gain"])
    return {
        "top_gain": ranked[:limit],
        "worst_gain": losers[:limit],
        "symbols_with_1_trade": sum(1 for c, rows in by_code.items() if len(rows) == 1),
        "symbols_with_2plus": sum(1 for c, rows in by_code.items() if len(rows) >= 2),
    }


def exit_reason_breakdown(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    closed = [t for t in trades if t.get("closed")]
    out: list[dict[str, Any]] = []
    counter = Counter(t.get("exit_reason") or "その他" for t in closed)
    for label in EXIT_LABELS:
        if not counter[label]:
            continue
        rows = [t for t in closed if (t.get("exit_reason") or "その他") == label]
        wins = sum(1 for t in rows if int(t["gain"]) > 0)
        out.append(
            {
                "reason": label,
                "count": len(rows),
                "share_pct": round(len(rows) / len(closed) * 100, 1) if closed else 0,
                "win_rate": round(wins / len(rows) * 100, 1) if rows else None,
                "total_gain": sum(int(t["gain"]) for t in rows),
                "avg_gain": round(sum(int(t["gain"]) for t in rows) / len(rows), 1),
            }
        )
    return out


def build_report(
    trades: list[dict[str, Any]],
    *,
    label: str,
    past_period_days: int,
    symbols_enabled: int,
    symbols_traded: int,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, Any]:
    summary = summarize_window(
        trades,
        label=label,
        past_period_days=past_period_days,
        symbols_enabled=symbols_enabled,
        symbols_traded=symbols_traded,
    )
    closed = [t for t in trades if t.get("closed")]
    entry_dates = [t["entry"][:7] for t in trades]
    return {
        "summary": asdict(summary),
        "period": {"start": period_start, "end": period_end},
        "by_year": aggregate_by_key(closed, lambda t: t["entry"][:4]),
        "by_month": aggregate_by_key(closed, lambda t: t["entry"][:7]),
        "by_quarter": aggregate_by_key(
            closed,
            lambda t: f"{t['entry'][:4]}-Q{(int(t['entry'][5:7]) - 1) // 3 + 1}",
        ),
        "exit_reasons": exit_reason_breakdown(trades),
        "hold_days": bucket_hold_days(trades),
        "symbols": top_symbols(trades),
        "entry_month_counts": dict(sorted(Counter(entry_dates).items())),
    }


def patch_config_past_period(config_text: str, past_period: int) -> str:
    if re.search(r"SCR_PAST_PERIOD\s*=", config_text):
        return re.sub(r"SCR_PAST_PERIOD\s*=\s*\d+", f"SCR_PAST_PERIOD = {past_period}", config_text)
    return config_text.replace("[SCREENING]", f"[SCREENING]\nSCR_PAST_PERIOD = {past_period}", 1)
