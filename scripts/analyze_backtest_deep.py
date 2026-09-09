#!/usr/bin/env python3
"""3年バックテストの深掘り分析（損切り・2025悪化・地合い・業種）."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from kaburadar3.analytics.backtest_deep import build_deep_report, load_code_metadata, load_market_closes
from kaburadar3.data import repository as db
from analyze_backtest_3y import DEFAULT_3Y_DAYS, run_window_backtest


def _print_stop_loss(report: dict) -> None:
    sl = report["stop_loss_analysis"]
    s = sl["summary"]
    print("\n" + "=" * 60)
    print("損切り vs RSI60")
    print("=" * 60)
    for key, label in (("stop_loss", "損切り"), ("rsi60", "RSI60")):
        row = s[key]
        print(
            f"  {label}: {row['count']}件  損益{row['total_gain']:,}円  "
            f"平均{row.get('avg_gain')}円  平均保有{row.get('avg_hold_days')}日  "
            f"中央保有{row.get('median_hold_days')}日"
        )
    print(f"  損切り比率: {s['stop_loss_share_pct']}%")

    print("\n[損切り・保有日数別]")
    for row in sl["stop_by_hold_days"]:
        print(
            f"  {row['key']}: {row['trades']}件  損益{row['total_gain']:,}円  "
            f"平均{row['avg_gain']}円"
        )

    print("\n[地合い別（全取引）]")
    for row in sl["all_by_market_regime"]:
        print(
            f"  {row['key']}: {row['trades']}件  勝率{row['win_rate']}%  PF{row['pf']}  "
            f"損切率{row['stop_loss_rate_pct']}%  損益{row['total_gain']:,}円"
        )

    print("\n[地合い別（損切りのみ）]")
    for row in sl["stop_by_market_regime"]:
        print(f"  {row['key']}: {row['trades']}件  損益{row['total_gain']:,}円")

    print("\n[業種・損切率が高い（5件以上）]")
    for row in sl["sector_high_stop_rate"][:8]:
        print(
            f"  {row['sector']}: 取引{row['trades']}  損切{row['stop_loss_count']} "
            f"({row['stop_loss_rate_pct']}%)  損切損益{row['stop_loss_gain']:,}円"
        )

    print("\n[繰返し損切り銘柄 TOP]")
    for row in sl["repeat_stop_loss_symbols"][:8]:
        print(
            f"  {row['code']} {row['name']}: 損切{row['stop_loss_count']}回  "
            f"合計{row['total_gain']:,}円  平均保有{row['avg_hold_days']}日"
        )

    print("\n[損切り最大 TOP5]")
    for row in sl["worst_stop_trades"][:5]:
        print(
            f"  {row['code']} {row['name']}: {row['entry']}→{row['exit']}  "
            f"{row['gain']:,}円 ({row['hold_days']}日)  {row.get('market_regime')}"
        )


def _print_year(report: dict) -> None:
    yd = report["year_deterioration"]
    print("\n" + "=" * 60)
    print("年次・2025悪化分析")
    print("=" * 60)
    for row in yd["by_year"]:
        print(
            f"  {row['year']}: {row['trades']}件  勝率{row['win_rate']}%  PF{row['pf']}  "
            f"損益{row['total_gain']:,}円  損切{row['stop_loss_count']}件({row['stop_loss_rate_pct']}%) "
            f"損切損{row['stop_loss_gain']:,} / RSI60+{row['rsi60_gain']:,}"
        )

    print("\n[2025 月別]")
    for row in yd["2025_months"]:
        print(
            f"  {row['label']}: {row['trades']}件  勝率{row['win_rate']}%  PF{row['pf']}  "
            f"損益{row['total_gain']:,}円  損切{row['stop_loss_count']}({row['stop_loss_rate_pct']}%)  "
            f"地合20d{row.get('avg_market_return_20d')}%"
        )

    cmp = yd["2025_vs_2024"]
    print("\n[2025 vs 2024]")
    print(
        f"  2024: PF{cmp['2024']['pf']}  損切平均{cmp['stop_loss_avg_gain_2024']}円/件\n"
        f"  2025: PF{cmp['2025']['pf']}  損切平均{cmp['stop_loss_avg_gain_2025']}円/件"
    )

    print("\n[悪化月 vs 地合い]")
    for row in yd["bad_months_vs_market"]:
        print(
            f"  {row['label']}: PF{row['pf']}  損益{row['total_gain']:,}円  "
            f"損切率{row['stop_loss_rate_pct']}%  地合20d{row.get('avg_market_return_20d')}%"
        )

    print("\n[2025-02 ワースト]")
    for row in yd["2025_02_worst_trades"][:8]:
        print(
            f"  {row['code']} {row['name']}: {row['gain']:,}円  "
            f"{row['exit_reason']} {row['hold_days']}日  {row.get('sector')}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="バックテスト深掘り分析")
    parser.add_argument("--days", type=int, default=DEFAULT_3Y_DAYS)
    parser.add_argument(
        "--trades",
        type=Path,
        default=ROOT / "output" / "backtest_3y" / "trades.json",
        help="取引JSON（なければバックテスト実行）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "backtest_3y" / "deep_report.json",
    )
    parser.add_argument("--rerun", action="store_true", help="trades.json があっても再実行")
    args = parser.parse_args(argv)

    if args.rerun or not args.trades.is_file():
        print(f"バックテスト実行中… past_period={args.days}")
        trades, *_ = run_window_backtest(args.days)
        args.trades.parent.mkdir(parents=True, exist_ok=True)
        args.trades.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"取引保存: {args.trades} ({len(trades)}件)")
    else:
        trades = json.loads(args.trades.read_text(encoding="utf-8"))
        print(f"取引読込: {args.trades} ({len(trades)}件)")

    conn, cursor = db.connect_db()
    try:
        metadata = load_code_metadata(cursor)
        market_closes = load_market_closes(cursor)
        report = build_deep_report(trades, metadata=metadata, market_closes=market_closes)
    finally:
        db.close_db(conn)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"深掘りレポート: {args.output}")

    _print_stop_loss(report)
    _print_year(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
