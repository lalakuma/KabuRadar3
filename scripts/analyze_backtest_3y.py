#!/usr/bin/env python3
"""約3年（SCR_PAST_PERIOD=1200）バックテストを実行し多面的に分析."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.backtest_report import build_report, extract_trades_from_outdf, patch_config_past_period
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf

DEFAULT_3Y_DAYS = 1200
DEFAULT_100D = 100


def _make_config(past_period: int) -> Path:
    text = patch_config_past_period((ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8"), past_period)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-bt-"))
    path = tmp / "config_lo.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _enabled_codes(conn, cursor) -> list:
    codes = db.read_code_all(cursor, "tbl_codelist")
    df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
    return [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]


def _trading_range(conn, cursor, sample_code: str = "7203") -> tuple[date | None, date | None]:
    cursor.execute(f'SELECT MIN(datetime), MAX(datetime) FROM "tbl_{sample_code}"')
    row = cursor.fetchone()
    if not row or not row[0]:
        return None, None
    start = datetime.fromisoformat(str(row[0])[:10]).date()
    end = datetime.fromisoformat(str(row[1])[:10]).date()
    return start, end


def run_window_backtest(past_period: int, *, limit: int | None = None) -> tuple[list[dict], int, int, date | None, date | None]:
    cfg = _make_config(past_period)
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    conn, cursor = db.connect_db()
    trades: list[dict] = []
    symbols_traded = 0
    try:
        enabled = _enabled_codes(conn, cursor)
        if limit:
            enabled = enabled[:limit]
        db_start, db_end = _trading_range(conn, cursor)
        scr = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
            past_period=-past_period,
            srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
            ent_rest=int(conf.get_config(scr, conf.CONF_KEY_SCR_ENTRY_REST)),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            for code in enabled:
                if engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor) == -1:
                    continue
                code_trades = extract_trades_from_outdf(str(code), prm.outdf)
                if code_trades:
                    symbols_traded += 1
                    trades.extend(code_trades)
    finally:
        db.close_db(conn)
        shutil.rmtree(cfg.parent, ignore_errors=True)

    period_start = min((t["entry"] for t in trades), default=None)
    period_end = max((t["exit"] or t["entry"] for t in trades if t.get("closed")), default=None)
    if not period_start and db_start:
        period_start = db_start.isoformat()
    if not period_end and db_end:
        period_end = db_end.isoformat()
    return trades, len(enabled), symbols_traded, (
        datetime.fromisoformat(str(period_start)).date() if period_start else db_start
    ), (datetime.fromisoformat(str(period_end)).date() if period_end else db_end)


def _print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(title)
    print("=" * 60)


def _print_report(report: dict) -> None:
    s = report["summary"]
    _print_section(f"{s['label']} サマリー")
    print(
        f"期間目安: {report['period'].get('start')} 〜 {report['period'].get('end')} "
        f"(past_period={s['past_period_days']} カレンダー日)"
    )
    print(
        f"銘柄: 有効 {s['symbols_enabled']} / 取引あり {s['symbols_traded']}  "
        f"エントリー {s['entries']}  決済 {s['closed']}  未決済 {s['open_count']}"
    )
    print(
        f"勝率 {s['win_rate']}%  PF {s['pf']}  損益 {s['total_gain']:,}円  "
        f"平均 {s['avg_gain']}円/件  中央値 {s['median_gain']}円"
    )
    print(
        f"平均勝ち {s['avg_win']}円  平均負け {s['avg_loss']}円  "
        f"最大 +{s['max_gain']:,} / {s['max_loss']:,}  平均保有 {s['avg_hold_days']}日"
    )

    print("\n[決済理由（推定）]")
    for row in report["exit_reasons"]:
        print(
            f"  {row['reason']}: {row['count']}件 ({row['share_pct']}%)  "
            f"勝率{row['win_rate']}%  損益{row['total_gain']:,}円  平均{row['avg_gain']}円"
        )

    print("\n[年別]")
    for row in report["by_year"]:
        print(
            f"  {row['key']}: {row['trades']}件  勝率{row['win_rate']}%  "
            f"PF{row['pf']}  損益{row['total_gain']:,}円"
        )

    print("\n[保有日数別]")
    for row in report["hold_days"]:
        print(
            f"  {row['bucket']}: {row['count']}件  勝率{row['win_rate']}%  損益{row['total_gain']:,}円"
        )

    sym = report["symbols"]
    print(f"\n[銘柄] 1回のみ {sym['symbols_with_1_trade']}銘柄 / 2回以上 {sym['symbols_with_2plus']}銘柄")
    print("  損益TOP5:")
    for row in sym["top_gain"][:5]:
        print(f"    {row['code']}: {row['trades']}件 PF{row['pf']} {row['total_gain']:,}円")
    print("  損益ワースト5:")
    for row in sym["worst_gain"][:5]:
        print(f"    {row['code']}: {row['trades']}件 PF{row['pf']} {row['total_gain']:,}円")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="3年バックテスト多面分析")
    parser.add_argument("--days", type=int, default=DEFAULT_3Y_DAYS, help="SCR_PAST_PERIOD（カレンダー日）")
    parser.add_argument("--compare-100", action="store_true", help="現行100日ウィンドウとも比較")
    parser.add_argument("--limit", type=int, default=None, help="銘柄数上限（デバッグ用）")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "backtest_3y" / "report.json",
        help="JSONレポート出力先",
    )
    args = parser.parse_args(argv)

    print(f"バックテスト実行中… past_period={args.days}（約3年≈1200）")
    trades, enabled, traded, p_start, p_end = run_window_backtest(args.days, limit=args.limit)
    report_3y = build_report(
        trades,
        label=f"約{args.days // 365}年" if args.days >= 365 else f"{args.days}日",
        past_period_days=args.days,
        symbols_enabled=enabled,
        symbols_traded=traded,
        period_start=p_start.isoformat() if p_start else None,
        period_end=p_end.isoformat() if p_end else None,
    )
    _print_report(report_3y)

    payload: dict = {"window_primary": report_3y}

    if args.compare_100:
        print("\n比較用 100日ウィンドウ実行中…")
        t100, en100, tr100, s100, e100 = run_window_backtest(DEFAULT_100D, limit=args.limit)
        report_100 = build_report(
            t100,
            label="100日（現行）",
            past_period_days=DEFAULT_100D,
            symbols_enabled=en100,
            symbols_traded=tr100,
            period_start=s100.isoformat() if s100 else None,
            period_end=e100.isoformat() if e100 else None,
        )
        _print_report(report_100)
        payload["window_100d"] = report_100
        payload["comparison"] = {
            "entries_ratio": round(report_3y["summary"]["entries"] / report_100["summary"]["entries"], 2)
            if report_100["summary"]["entries"]
            else None,
            "pf_3y": report_3y["summary"]["pf"],
            "pf_100d": report_100["summary"]["pf"],
            "win_rate_3y": report_3y["summary"]["win_rate"],
            "win_rate_100d": report_100["summary"]["win_rate"],
            "total_gain_3y": report_3y["summary"]["total_gain"],
            "total_gain_100d": report_100["summary"]["total_gain"],
        }
        print("\n[3年 vs 100日]")
        c = payload["comparison"]
        print(
            f"  エントリー倍率: {c['entries_ratio']}x  "
            f"PF {c['pf_3y']} vs {c['pf_100d']}  "
            f"勝率 {c['win_rate_3y']}% vs {c['win_rate_100d']}%  "
            f"損益 {c['total_gain_3y']:,} vs {c['total_gain_100d']:,}円"
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nレポート保存: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
