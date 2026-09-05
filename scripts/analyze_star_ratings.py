#!/usr/bin/env python3
"""星評価（★1-5）の予測力をバックテスト結果と結合して分析."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.star_ratings import analyze_star_ratings
from kaburadar3.analytics.trades import extract_trades_from_results
from kaburadar3.qualitative.rater import CACHE_FILE, load_cache
from kaburadar3.qualitative.rating_history import HISTORY_FILE, build_rating_lookup, load_history
from kaburadar3.settings.loader import read_path_config
from kaburadar3.settings.paths import PROJECT_ROOT


def _print_report(report: dict) -> None:
    summary = report["summary"]
    print("=== 星評価バックテスト ===")
    print(
        f"エントリー: {summary['total_entries']}  "
        f"評価あり: {summary['rated_entries']}  "
        f"評価なし: {summary['unrated_entries']}  "
        f"決済済み(評価あり): {summary['closed_rated']}"
    )
    if not summary["sample_sufficient"]:
        print(
            f"※ 決済済み {summary['closed_rated']} 件 "
            f"(最低 {summary['min_total_closed']} 件)。参考値として表示します。"
        )

    print("\n[星別]")
    for row in report["by_stars"]:
        ok = "OK" if row["sample_ok"] else "不足"
        wr = f"{row['win_rate']:.1f}%" if row["win_rate"] is not None else "-"
        pf = f"{row['pf']:.2f}" if row["pf"] is not None else "-"
        avg = f"{row['avg_gain']:,.0f}" if row["avg_gain"] is not None else "-"
        print(
            f"  ★{row['stars']}: 決済 {row['closed']} ({ok})  "
            f"勝率 {wr}  PF {pf}  損益 {row['total_gain']:,}  平均 {avg}"
        )

    print("\n[戦略比較]")
    for row in report["strategies"]:
        wr = f"{row['win_rate']:.1f}%" if row["win_rate"] is not None else "-"
        pf = f"{row['pf']:.2f}" if row["pf"] is not None else "-"
        print(
            f"  {row['name']}: エントリー {row['entries']}  決済 {row['closed']}  "
            f"勝率 {wr}  PF {pf}  損益 {row['total_gain']:,}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="星評価の予測力をバックテスト")
    parser.add_argument(
        "--results",
        type=Path,
        default=None,
        help="code*.csv があるフォルダ（既定: config PATH_HONBAN）",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=CACHE_FILE,
        help="quality_cache.json のパス",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=HISTORY_FILE,
        help="signal_ratings.jsonl のパス",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "output" / "results" / "star_rating_report.json",
        help="JSON レポート出力先",
    )
    args = parser.parse_args(argv)

    results_dir = args.results or Path(read_path_config("SHUUKEI", "PATH_HONBAN"))
    if not results_dir.is_dir():
        print(f"結果フォルダがありません: {results_dir}", file=sys.stderr)
        return 1

    cache = load_cache(args.cache)
    history = load_history(args.history)
    lookup = build_rating_lookup(cache=cache, history=history)
    trades = extract_trades_from_results(results_dir)
    report = analyze_star_ratings(trades, lookup)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"レポート: {args.output}")
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
