"""8件以上シグナル日の分析 + ETF(1306)の短期リターン."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "src")
from kaburadar3.analytics.backtest_deep import load_market_closes
from kaburadar3.data import repository as db

trades = json.loads(Path("output/backtest_10y/trades.json").read_text(encoding="utf-8"))
by_day: dict[str, list] = defaultdict(list)
for t in trades:
    by_day[t["entry"][:10]].append(t)
dc = Counter(t["entry"][:10] for t in trades)

conn, cursor = db.connect_db()
etf = load_market_closes(cursor, "1306")  # 野村東証指数
db.close_db(conn)


def forward_return(entry: str, hold_days: int = 5) -> float | None:
    d = date.fromisoformat(entry[:10])
    if d not in etf:
        return None
    dates = sorted(x for x in etf if x >= d)
    if len(dates) <= hold_days:
        return None
    p0 = etf[dates[0]]
    p1 = etf[dates[hold_days]]
    return (p1 - p0) / p0 * 100 if p0 else None


TH = 8
days8 = [d for d, n in dc.items() if n >= TH]
days_lt = [d for d, n in dc.items() if n < TH]

print(f"=== 新買シグナル {TH}件以上の日 ===")
print(f"10年で {len(days8)} 日 / 全{len(dc)}日 ({len(days8)/len(dc)*100:.1f}%)")
print(f"1年あたり約 {len(days8)/10:.1f} 日\n")

# 個別シグナルの成績
for label, days in (f"{TH}件以上", days8), (f"{TH}件未満", days_lt):
    rows = [t for t in trades if t.get("closed") and t["entry"][:10] in days]
    wins = sum(1 for t in rows if int(t["gain"]) > 0)
    total = sum(int(t["gain"]) for t in rows)
    avg = total / len(rows) if rows else 0
    wr = wins / len(rows) * 100 if rows else 0
    print(f"[個別100株ルール・{label}] 決済{len(rows)}  勝率{wr:.1f}%  合計{total:,}  平均{avg:,.0f}/件")

# ETF 5日ホールド（500k想定の%のみ）
print(f"\n[1306 ETF エントリー日から5営業日後リターン]")
for label, days in (f"{TH}件以上", days8), (f"{TH}件未満", days_lt):
    rets = [forward_return(d, 5) for d in days]
    rets = [r for r in rets if r is not None]
    if not rets:
        continue
    avg = sum(rets) / len(rets)
    win = sum(1 for r in rets if r > 0) / len(rets) * 100
    print(f"  {label}: {len(rets)}日  勝率{win:.1f}%  平均{avg:+.2f}%  (50万なら約{500000*avg/100:+.0f}円)")

print(f"\n=== {TH}件以上の日（損益ワースト5 / ベスト5） ===")
day_pnl = []
for d in days8:
    rows = by_day[d]
    g = sum(int(t["gain"]) for t in rows if t.get("closed"))
    er = forward_return(d, 5)
    day_pnl.append((d, dc[d], g, er))
for d, n, g, er in sorted(day_pnl, key=lambda x: x[2])[:5]:
    es = f"ETF5d {er:+.1f}%" if er is not None else "ETF n/a"
    print(f"  {d}  新買{n:3}  個別合計{g:+,}  {es}")
print("  ---")
for d, n, g, er in sorted(day_pnl, key=lambda x: -x[2])[:5]:
    es = f"ETF5d {er:+.1f}%" if er is not None else "ETF n/a"
    print(f"  {d}  新買{n:3}  個別合計{g:+,}  {es}")

print(f"\n=== 2020/3/2, 3/10 ===")
for d in ("2020-03-02", "2020-03-10"):
    if d not in dc:
        continue
    rows = by_day[d]
    g = sum(int(t["gain"]) for t in rows if t.get("closed"))
    wins = sum(1 for t in rows if int(t["gain"]) > 0)
    er5 = forward_return(d, 5)
    print(f"  {d}  新買{dc[d]}  個別勝{wins}/{len(rows)}  合計{g:+,}  ETF5d {er5:+.2f}%" if er5 else f"  {d}  新買{dc[d]}")
