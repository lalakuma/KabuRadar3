#!/usr/bin/env python3
"""特定年のバックテストを詳細分解."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.backtest_deep import load_code_metadata, load_market_closes
from kaburadar3.analytics.backtest_year_breakdown import build_year_breakdown
from kaburadar3.data import repository as db


def _print_months(rows: list[dict]) -> None:
    print(f"{'月':<10} {'件':>4} {'勝率':>6} {'PF':>6} {'損益':>10} {'損切':>4} {'損切率':>6} {'地合20d':>8}")
    for r in rows:
        pf = f"{r['pf']:.2f}" if r.get("pf") is not None else "-"
        mkt = r.get("market_avg_20d")
        mkt_s = f"{mkt:+.1f}%" if mkt is not None else "-"
        print(
            f"{r['month']:<10} {r['trades']:>4} {r['win_rate']:>5.1f}% {pf:>6} "
            f"{r['total_gain']:>10,} {r['stop_loss_count']:>4} {r['stop_loss_rate_pct']:>5.1f}% {mkt_s:>8}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="年次バックテスト詳細分解")
    parser.add_argument("--year", type=int, default=2020)
    parser.add_argument(
        "--trades",
        type=Path,
        default=ROOT / "output" / "backtest_10y" / "trades.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON出力（既定: output/backtest_10y/breakdown_{year}.json）",
    )
    args = parser.parse_args(argv)
    out_path = args.output or (ROOT / "output" / "backtest_10y" / f"breakdown_{args.year}.json")

    if not args.trades.is_file():
        print(f"取引ファイルがありません: {args.trades}", file=sys.stderr)
        return 1

    trades = json.loads(args.trades.read_text(encoding="utf-8"))
    conn, cursor = db.connect_db()
    try:
        metadata = load_code_metadata(cursor)
        market_closes = load_market_closes(cursor)
        report = build_year_breakdown(
            trades,
            year=args.year,
            metadata=metadata,
            market_closes=market_closes,
            compare_years=[args.year - 1, args.year + 1],
        )
    finally:
        db.close_db(conn)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    s = report["summary"]
    print(f"=== {args.year}年 詳細分解 ===")
    print(
        f"決済 {s['trades']}件  勝率{s['win_rate']}%  PF{s['pf']}  損益{s['total_gain']:,}円\n"
        f"損切 {s['stop_loss_count']}件({s['stop_loss_rate_pct']}%) → {s['stop_loss_gain']:,}円  "
        f"RSI60 {s['rsi60_count']}件 → +{s['rsi60_gain']:,}円"
    )

    print("\n[月別]")
    _print_months(report["by_month"])

    print("\n[四半期]")
    for r in report["by_quarter"]:
        print(
            f"  {r['key']}: {r['trades']}件  PF{r['pf']}  損益{r['total_gain']:,}円  "
            f"損切率{r['stop_loss_rate_pct']}%"
        )

    cw = report["covid_window_feb_apr"]
    print(f"\n[COVID窗口 2〜4月] {cw['trades']}件  PF{cw.get('pf')}  損益{cw['total_gain']:,}円  損切率{cw.get('stop_loss_rate_pct')}%")

    print("\n[地合い別（エントリー日）]")
    for r in report["by_market_regime"]:
        print(
            f"  {r['key']}: {r['trades']}件  PF{r['pf']}  損切率{r['stop_loss_rate_pct']}%  損益{r['total_gain']:,}円"
        )

    print("\n[損切り・保有日数]")
    for r in report["stop_loss_by_hold"]:
        print(f"  {r['key']}: {r['trades']}件  損益{r['total_gain']:,}円  平均{r['avg_gain']}円")

    print("\n[年比較]")
    for r in report["year_compare"]:
        print(
            f"  {r['year']}: {r['trades']}件  勝率{r['win_rate']}%  PF{r['pf']}  "
            f"損益{r['total_gain']:,}円  損切率{r['stop_loss_rate_pct']}%"
        )

    print("\n[損切り多い銘柄 TOP8]")
    for r in report["top_stop_symbols"][:8]:
        print(f"  {r['code']} {r['name']}: 損切{r['stop_loss_count']}回  {r['total_gain']:,}円")

    print("\n[ワースト取引 TOP8]")
    for r in report["worst_trades"][:8]:
        print(
            f"  {r['code']} {r['name']}: {r['entry']}→{r['exit']}  {r['gain']:,}円  "
            f"{r.get('exit_reason')}  {r.get('market_regime')}"
        )

    print(f"\nJSON: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
