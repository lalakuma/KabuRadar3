#!/usr/bin/env python3
"""地合い（20日リターン）のみでエントリー停止した場合のシミュレーション."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.backtest_deep import load_market_closes, market_return_at
from kaburadar3.analytics.backtest_report import _calc_pf
from kaburadar3.data import repository as db


def main() -> int:
    trades = json.loads((ROOT / "output" / "backtest_10y" / "trades.json").read_text(encoding="utf-8"))
    by_day: dict[str, list] = defaultdict(list)
    for t in trades:
        by_day[t["entry"][:10]].append(t)

    conn, cursor = db.connect_db()
    market = load_market_closes(cursor)
    db.close_db(conn)

    def mkt(d: str) -> float | None:
        return market_return_at(market, date.fromisoformat(d))

    # エントリー日ごとの地合い
    entry_days = sorted(by_day.keys())
    baseline = sum(int(t["gain"]) for t in trades if t.get("closed"))

    print("=== 地合い20日リターンのみ（件数条件なし） ===")
    print("ルール: エントリー日の地合20d が閾値未満 → その日は全銘柄エントリー停止\n")
    print(f"{'閾値':<12} {'停止日':>6} {'残ENTRY':>8} {'PF':>6} {'損益':>12} {'差分':>10} 3/2 3/10 3/17")
    for th in [-5, -6, -7, -8, -9, -10, -12, -15, -18, -20, -25]:
        block = {d for d in entry_days if (mkt(d) is not None and mkt(d) < th)}
        kept = [t for t in trades if t["entry"][:10] not in block]
        closed = [t for t in kept if t.get("closed")]
        wins = [t for t in closed if int(t["gain"]) > 0]
        losses = [t for t in closed if int(t["gain"]) < 0]
        total = sum(int(t["gain"]) for t in closed)
        pf = _calc_pf(wins, losses)
        delta = total - baseline
        h = lambda d: "✓" if d in block else "-"
        print(
            f"地合20d<{th:3}% {len(block):6} {len(kept):8} {pf:6.3f} "
            f"{total:12,} {delta:+10,} {h('2020-03-02'):>3} {h('2020-03-10'):>4} {h('2020-03-17'):>4}"
        )

    # 停止日の損益内訳（代表閾値）
    print("\n=== 地合20d < -10% で止めた日（損益ワースト10 / ベスト5） ===")
    th = -10
    block = {d for d in entry_days if (mkt(d) is not None and mkt(d) < th)}
    day_pnl = []
    for d in block:
        gain = sum(int(t["gain"]) for t in by_day[d] if t.get("closed"))
        day_pnl.append((d, len(by_day[d]), gain, mkt(d)))
    day_pnl.sort(key=lambda x: x[2])
    print("[止めた日・ワースト]")
    for d, n, g, m in day_pnl[:10]:
        print(f"  {d}  新買{n:3}  損益{g:+,}  地合{m:+.1f}%")
    print("[止めた日・ベスト＝逃した利益]")
    for d, n, g, m in sorted(day_pnl, key=lambda x: -x[2])[:5]:
        print(f"  {d}  新買{n:3}  損益{g:+,}  地合{m:+.1f}%")

    # 2020年3月 地合いだけ見る
    print("\n=== 2020年3月（地合20d と損益） ===")
    for d in sorted(by_day):
        if not d.startswith("2020-03"):
            continue
        g = sum(int(t["gain"]) for t in by_day[d] if t.get("closed"))
        m = mkt(d)
        flags = []
        if m is not None and m < -10:
            flags.append("止<-10%")
        if m is not None and m < -18:
            flags.append("止<-18%")
        print(f"  {d}  新買{len(by_day[d]):3}  損益{g:+,}  地合{m:+.1f}%  {' '.join(flags)}")

    # 地合い vs 件数の判別力（8日の50+日）
    print("\n=== 新買50件以上の8日 — 地合20d ===")
    dc = Counter(t["entry"][:10] for t in trades)
    for d, cnt in sorted(((d, c) for d, c in dc.items() if c >= 50), key=lambda x: -x[1]):
        g = sum(int(t["gain"]) for t in by_day[d] if t.get("closed"))
        m = mkt(d)
        print(f"  {d}  新買{cnt:3}  損益{g:+,}  地合{m:+.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
