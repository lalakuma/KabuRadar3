#!/usr/bin/env python3
"""同日新買シグナル数（広がり）フィルターの閾値スイープ."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.backtest_deep import load_market_closes, market_return_at
from kaburadar3.analytics.backtest_report import _calc_pf
from kaburadar3.data import repository as db


def _parse(entry: str) -> date:
    return date.fromisoformat(entry[:10])


def _summarize(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("closed")]
    wins = [t for t in closed if int(t["gain"]) > 0]
    losses = [t for t in closed if int(t["gain"]) < 0]
    return {
        "entries": len(trades),
        "closed": len(closed),
        "win_rate": round(len(wins) / len(closed) * 100, 2) if closed else None,
        "pf": _calc_pf(wins, losses),
        "total_gain": sum(int(t["gain"]) for t in closed),
    }


def main() -> int:
    trades_path = ROOT / "output" / "backtest_10y" / "trades.json"
    trades = json.loads(trades_path.read_text(encoding="utf-8"))

    daily_count: Counter = Counter()
    by_day: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        d = t["entry"][:10]
        daily_count[d] += 1
        by_day[d].append(t)

    conn, cursor = db.connect_db()
    try:
        market = load_market_closes(cursor)
    finally:
        db.close_db(conn)

    def mkt20(d: str) -> float | None:
        return market_return_at(market, date.fromisoformat(d))

    baseline = _summarize(trades)
    print("=== ベースライン（10年） ===")
    print(
        f"  エントリー {baseline['entries']}  PF {baseline['pf']}  "
        f"損益 {baseline['total_gain']:,}  勝率 {baseline['win_rate']}%"
    )

    focus = ("2020-03-02", "2020-03-10")
    print("\n=== 閾値スイープ: 同日新買 N 件以上 → その日は全銘柄エントリー停止 ===")
    print(f"{'閾値':>4} {'停止日':>6} {'残ENTRY':>8} {'PF':>6} {'損益':>12} {'差分':>10} {'2020/3/2':>8} {'2020/3/10':>8}")
    thresholds = [10, 12, 15, 18, 20, 25, 30, 40, 50, 60, 80]
    best_candidates = []
    for n in thresholds:
        block_days = {d for d, c in daily_count.items() if c >= n}
        kept = [t for t in trades if t["entry"][:10] not in block_days]
        s = _summarize(kept)
        delta = s["total_gain"] - baseline["total_gain"]
        hit2 = "✓" if "2020-03-02" in block_days else "-"
        hit10 = "✓" if "2020-03-10" in block_days else "-"
        print(
            f"{n:4} {len(block_days):6} {s['entries']:8} {s['pf']:6.3f} "
            f"{s['total_gain']:12,} {delta:+10,} {hit2:>8} {hit10:>8}"
        )
        best_candidates.append((n, len(block_days), delta, s["pf"], block_days))

    # 複合ルール
    print("\n=== 複合ルール（精度重視案） ===")
    rules = [
        ("新買>=15", lambda d, c: c >= 15),
        ("新買>=20", lambda d, c: c >= 20),
        ("新買>=15 且つ 地合20d<-5%", lambda d, c: c >= 15 and (mkt20(d) or 0) < -5),
        ("新買>=15 且つ 地合20d<-8%", lambda d, c: c >= 15 and (mkt20(d) or 0) < -8),
        ("新買>=12 且つ 地合20d<-10%", lambda d, c: c >= 12 and (mkt20(d) or 0) < -10),
        ("新買>=20 或いは 地合20d<-12%", lambda d, c: c >= 20 or (mkt20(d) or 0) < -12),
        ("新買>=25", lambda d, c: c >= 25),
        ("新買>=30", lambda d, c: c >= 30),
    ]
    print(f"{'ルール':<28} {'停止日':>5} {'PF':>6} {'損益':>12} {'差分':>10} {'3/2':>3} {'3/10':>4}")
    for name, pred in rules:
        block_days = {d for d, c in daily_count.items() if pred(d, c)}
        kept = [t for t in trades if t["entry"][:10] not in block_days]
        s = _summarize(kept)
        delta = s["total_gain"] - baseline["total_gain"]
        print(
            f"{name:<28} {len(block_days):5} {s['pf']:6.3f} {s['total_gain']:12,} {delta:+10,} "
            f"{'✓' if '2020-03-02' in block_days else '-':>3} "
            f"{'✓' if '2020-03-10' in block_days else '-':>4}"
        )

    # 停止日の質: 止めた日の損益 vs 逃した利益
    print("\n=== 閾値15: 停止した日の内訳（損益順ワースト10） ===")
    n = 15
    block_days = {d for d, c in daily_count.items() if c >= n}
    day_pnl = []
    for d in block_days:
        rows = by_day[d]
        closed = [t for t in rows if t.get("closed")]
        gain = sum(int(t["gain"]) for t in closed)
        day_pnl.append((d, daily_count[d], gain, mkt20(d)))
    day_pnl.sort(key=lambda x: x[2])
    for d, cnt, gain, mkt in day_pnl[:10]:
        mkt_s = f"{mkt:+.1f}%" if mkt is not None else "-"
        print(f"  {d}  新買{cnt:3}件  損益{gain:+,}  地合20d {mkt_s}")

    print("\n=== 閾値15: 停止した日の内訳（利益だった日＝逃したチャンス TOP8） ===")
    good_blocked = sorted([(d, c, g) for d, c, g, _ in day_pnl if g > 0], key=lambda x: -x[2])[:8]
    for d, cnt, gain in good_blocked:
        print(f"  {d}  新買{cnt:3}件  損益+{gain:,}  ← この日は止めると機会損失")

    # 2020年3月の日別
    print("\n=== 2020年3月 日別（新買件数・損益・地合20d） ===")
    for d in sorted(by_day):
        if not d.startswith("2020-03"):
            continue
        rows = by_day[d]
        gain = sum(int(t["gain"]) for t in rows if t.get("closed"))
        mkt = mkt20(d)
        mkt_s = f"{mkt:+.1f}%" if mkt is not None else "-"
        flag = " ***" if daily_count[d] >= 15 else ""
        print(f"  {d}  新買{daily_count[d]:3}  損益{gain:+,}  地合20d {mkt_s}{flag}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
