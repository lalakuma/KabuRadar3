#!/usr/bin/env python3
"""50万/日・RCI上向き+RSI低順・1〜2銘柄の10年ポートフォリオシミュ."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from kaburadar3.analytics.backtest_report import _calc_pf
from kaburadar3.data import repository as db
from kaburadar3.signals.picker import PICK_RCI_RSI, enrich_trades_by_code, pick_trades

from simulate_realistic_500k import MAX_STOCKS, SimTrade, stock_batch_pnl, summarize

CAPITAL_LIMIT = 500_000


def run_stock_only_rci(
    by_day: dict[str, list[dict]],
    *,
    capital: float = CAPITAL_LIMIT,
) -> list[SimTrade]:
    """常に個別1〜2（RCI+RSI選定）、同時1ポジション."""
    out: list[SimTrade] = []
    busy_until: date | None = None

    for day_s in sorted(by_day):
        day = date.fromisoformat(day_s)
        if busy_until and day <= busy_until:
            continue
        rows = [t for t in by_day[day_s] if t.get("closed")]
        if not rows:
            continue

        picks = pick_trades(rows, n=MAX_STOCKS, method=PICK_RCI_RSI, capital=capital)
        if not picks:
            continue

        total_deploy = sum(
            int((capital // len(picks)) // (float(p["buy_price"]) * 100)) * 100 * float(p["buy_price"])
            for p in picks
            if float(p.get("buy_price", 0)) > 0
        )
        if total_deploy > capital:
            continue

        pnl, avg_buy, avg_exit, hold, reason = stock_batch_pnl(picks, capital)
        busy_until = max(date.fromisoformat(t["exit"][:10]) for t in picks)
        out.append(
            SimTrade(
                entry=day_s,
                exit=busy_until.isoformat(),
                kind="stock",
                codes=[t["code"] for t in picks],
                buy_price=avg_buy,
                exit_price=avg_exit,
                pnl=pnl,
                hold_days=hold,
                exit_reason=reason,
                signal_count=len(rows),
            )
        )
    return out


def year_breakdown(sim: list[SimTrade]) -> list[dict]:
    by_year: dict[str, list[SimTrade]] = defaultdict(list)
    for t in sim:
        by_year[t.entry[:4]].append(t)
    rows = []
    for y in sorted(by_year):
        g = by_year[y]
        wins = [x for x in g if x.pnl > 0]
        losses = [x for x in g if x.pnl < 0]
        total = sum(x.pnl for x in g)
        rows.append(
            {
                "year": y,
                "trades": len(g),
                "win_rate": round(len(wins) / len(g) * 100, 1) if g else 0,
                "pf": _calc_pf([{"gain": x.pnl} for x in wins], [{"gain": x.pnl} for x in losses]),
                "total_pnl": total,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trades",
        default=str(ROOT / "output" / "optimize" / "trades_損切7%.json"),
    )
    parser.add_argument("--capital", type=int, default=CAPITAL_LIMIT)
    parser.add_argument("--output", default=str(ROOT / "output" / "backtest_500k_rci_rsi" / "report.json"))
    args = parser.parse_args()

    trades_path = Path(args.trades)
    if not trades_path.is_file():
        trades_path = ROOT / "output" / "backtest_10y" / "trades.json"
    print("=" * 60)
    print("50万/日バックテスト（RCI上向き + RSI低順・1〜2銘柄）")
    print("=" * 60)
    print(f"  trades: {trades_path}")
    print(f"  資金/日: {args.capital:,}円以下（100株単位）")
    print(f"  選定: RCI上向き優先 → RSI4低い順 → 最大2銘柄均等")
    print(f"  制約: 同時1ポジション（保有中はスキップ）")
    print(f"  ETF・8件ルール: なし（個別のみ）")
    print()

    trades = json.loads(trades_path.read_text(encoding="utf-8"))
    conn, cursor = db.connect_db()
    try:
        print("エントリー日テクニカル付与中…")
        enriched = enrich_trades_by_code(trades, conn, cursor)
    finally:
        db.close_db(conn)

    by_day: dict[str, list[dict]] = defaultdict(list)
    for t in enriched:
        if t.get("closed"):
            by_day[t["entry"][:10]].append(t)

    sim = run_stock_only_rci(by_day, capital=float(args.capital))
    summarize(sim, f"50万・RCI+RSI（{args.capital//10000}万）")

    years = year_breakdown(sim)
    print("\n[年別]")
    for r in years:
        print(f"  {r['year']}: {r['trades']}件  勝率{r['win_rate']}%  PF{r['pf']}  {r['total_pnl']:+,}円")

    wins = [t for t in sim if t.pnl > 0]
    losses = [t for t in sim if t.pnl < 0]
    total = sum(t.pnl for t in sim)
    pf = _calc_pf([{"gain": t.pnl} for t in wins], [{"gain": t.pnl} for t in losses])

    print("\n[2020年3月]")
    m3 = [t for t in sim if t.entry.startswith("2020-03")]
    print(f"  件数 {len(m3)}  損益 {sum(t.pnl for t in m3):+,}円")

    print("\n[ワースト5]")
    for t in sorted(sim, key=lambda x: x.pnl)[:5]:
        print(
            f"  {t.entry}  通知{t.signal_count}  {','.join(t.codes)}  "
            f"{t.pnl:+,}円  {t.hold_days}日  {t.exit_reason}"
        )
    print("[ベスト5]")
    for t in sorted(sim, key=lambda x: -x.pnl)[:5]:
        print(
            f"  {t.entry}  通知{t.signal_count}  {','.join(t.codes)}  "
            f"{t.pnl:+,}円  {t.hold_days}日  {t.exit_reason}"
        )

    payload = {
        "assumptions": {
            "capital_per_day_max": args.capital,
            "pick_method": PICK_RCI_RSI,
            "max_stocks": MAX_STOCKS,
            "single_position": True,
            "etf_rule": False,
            "trades_source": str(trades_path),
        },
        "summary": {
            "trades": len(sim),
            "win_rate": round(len(wins) / len(sim) * 100, 1) if sim else 0,
            "pf": pf,
            "total_pnl": total,
            "avg_pnl": round(total / len(sim)) if sim else 0,
            "median_pnl": median(t.pnl for t in sim) if sim else 0,
            "max_loss": min((t.pnl for t in sim), default=0),
            "max_gain": max((t.pnl for t in sim), default=0),
        },
        "by_year": years,
        "trades": [t.__dict__ for t in sim],
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
