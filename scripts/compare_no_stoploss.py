#!/usr/bin/env python3
"""損切りOFF（RSI60 / 100日のみ）vs 現行（-3%損切りあり）の10年比較."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
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


def patch_config(
    config_text: str,
    *,
    past_period: int | None = None,
    stop_loss: bool | None = None,
) -> str:
    text = patch_config_past_period(config_text, past_period) if past_period is not None else config_text
    if stop_loss is not None:
        val = 1 if stop_loss else 0
        if re.search(r"SCR_JDG_STOP_LOSS\s*=", text):
            text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", f"SCR_JDG_STOP_LOSS = {val}", text)
        else:
            text = text.replace("[SCREENING]", f"[SCREENING]\nSCR_JDG_STOP_LOSS = {val}", 1)
    return text


def _make_config(past_period: int, *, stop_loss: bool) -> Path:
    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch_config(base, past_period=past_period, stop_loss=stop_loss)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-sl-"))
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


def run_backtest(past_period: int, *, stop_loss: bool, limit: int | None = None) -> tuple[list[dict], dict]:
    cfg = _make_config(past_period, stop_loss=stop_loss)
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
    report = build_report(
        trades,
        label="no_stop" if not stop_loss else "baseline",
        past_period_days=past_period,
        symbols_enabled=len(enabled),
        symbols_traded=symbols_traded,
        period_start=period_start,
        period_end=period_end or (db_end.isoformat() if db_end else None),
    )
    meta = {
        "stop_loss": stop_loss,
        "jdg_stop_loss": int(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_JDG_STOP_LOSS)),
        "stop_loss_pct": float(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_STOP_LOSS_PCT, default="3")),
        "srsi_hi": int(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_SRSI_HI)),
        "sell_period": int(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_SELL_PERIOD)),
    }
    return trades, {"report": report, "meta": meta}


def _print_summary(label: str, report: dict) -> None:
    s = report["summary"]
    print(f"\n[{label}]")
    print(
        f"  エントリー {s['entries']}  決済 {s['closed']}  "
        f"勝率 {s['win_rate']}%  PF {s['pf']}  損益 {s['total_gain']:,}円"
    )
    print(f"  平均 {s['avg_gain']}円/件  最大 +{s['max_gain']:,} / {s['max_loss']:,}  平均保有 {s['avg_hold_days']}日")
    print("  決済理由:")
    for row in report["exit_reasons"]:
        print(
            f"    {row['reason']}: {row['count']}件 ({row['share_pct']}%)  "
            f"損益{row['total_gain']:,}円"
        )
    print("  年別:")
    for row in report["by_year"]:
        print(f"    {row['key']}: {row['trades']}件 PF{row['pf']} {row['total_gain']:,}円")


def main() -> int:
    parser = argparse.ArgumentParser(description="損切りOFF vs 現行バックテスト比較")
    parser.add_argument("--days", type=int, default=3650)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--baseline-trades",
        type=Path,
        default=ROOT / "output" / "backtest_10y" / "trades.json",
        help="既存の現行 trades.json（あれば再実行を省略）",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "backtest_no_stoploss")
    args = parser.parse_args()

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== 損切りOFF vs 現行（past_period={args.days}） ===")
    print("変更: SCR_JDG_STOP_LOSS = 0（RSI60 / 100日のみ決済）")

    baseline_report = None
    if args.baseline_trades.is_file() and args.days == 3650 and not args.limit:
        print(f"\n現行: 既存 {args.baseline_trades} を使用")
        baseline_trades = json.loads(args.baseline_trades.read_text(encoding="utf-8"))
        baseline_report = build_report(
            baseline_trades,
            label="現行（損切り-3%）",
            past_period_days=args.days,
            symbols_enabled=0,
            symbols_traded=0,
            period_start=min(t["entry"] for t in baseline_trades) if baseline_trades else None,
            period_end=max(t["exit"] for t in baseline_trades if t.get("closed")) if baseline_trades else None,
        )
    else:
        print("\n現行: バックテスト実行中…")
        baseline_trades, payload = run_backtest(args.days, stop_loss=True, limit=args.limit)
        baseline_report = payload["report"]
        (out_dir / "trades_baseline.json").write_text(
            json.dumps(baseline_trades, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print("\n損切りOFF: バックテスト実行中…")
    no_stop_trades, no_stop_payload = run_backtest(args.days, stop_loss=False, limit=args.limit)
    no_stop_report = no_stop_payload["report"]
    (out_dir / "trades_no_stoploss.json").write_text(
        json.dumps(no_stop_trades, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _print_summary("現行（損切り-3%あり）", baseline_report)
    _print_summary("損切りOFF（RSI60/100日のみ）", no_stop_report)

    bs = baseline_report["summary"]
    ns = no_stop_report["summary"]
    print("\n[差分] 損切りOFF - 現行")
    print(f"  損益: {ns['total_gain'] - bs['total_gain']:+,}円")
    print(f"  PF: {ns['pf']} vs {bs['pf']}  (差 {round((ns['pf'] or 0) - (bs['pf'] or 0), 3)})")
    print(f"  勝率: {ns['win_rate']}% vs {bs['win_rate']}%")
    print(f"  決済数: {ns['closed']} vs {bs['closed']}")

    # 2020年比較
    def year_gain(report: dict, year: str) -> int:
        for row in report["by_year"]:
            if row["key"] == year:
                return row["total_gain"]
        return 0

    print("\n[2020年]")
    print(f"  現行: {year_gain(baseline_report, '2020'):,}円")
    print(f"  損切りOFF: {year_gain(no_stop_report, '2020'):,}円")

    comparison = {
        "baseline": baseline_report,
        "no_stoploss": no_stop_report,
        "delta": {
            "total_gain": ns["total_gain"] - bs["total_gain"],
            "pf_baseline": bs["pf"],
            "pf_no_stop": ns["pf"],
            "closed_baseline": bs["closed"],
            "closed_no_stop": ns["closed"],
        },
    }
    (out_dir / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存: {out_dir / 'comparison.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
