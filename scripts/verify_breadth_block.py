#!/usr/bin/env python3
"""新買 N 件以上の日は RCI エントリー停止 — バックテスト比較."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import tempfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf


def _row_date(row, idx) -> date:
    dt = row.get("Index", row.get("datetime", idx))
    if isinstance(dt, datetime):
        return dt.date()
    if isinstance(dt, date):
        return dt
    return datetime.fromisoformat(str(dt)[:10]).date()


def _make_rci_config() -> Path:
    text = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-breadth-"))
    (tmp / "config_lo.ini").write_text(text, encoding="utf-8")
    return tmp / "config_lo.ini"


def _run(enabled: list, as_of: date, block_dates: set[date] | None) -> dict:
    cfg = _make_rci_config()
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    scr = conf.CONF_SEC_SCR
    window = int(conf.get_config(scr, conf.CONF_KEY_SCR_PAST_PERIOD))
    prm = KabInf(
        sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
        past_period=-window,
        srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
        srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
        as_of_date=as_of,
        breadth_block_dates=block_dates,
    )
    entries = closed = wins = losses = income = 0
    conn, cursor = db.connect_db()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for code in enabled:
                if engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor) == -1:
                    continue
                df = prm.outdf
                if df is None or df.empty:
                    continue
                entries += int((df["mark"] == "新買").sum())
                for _, row in df[df["mark"] == "返売"].iterrows():
                    g = int(row["buygain"])
                    closed += 1
                    income += g
                    if g > 0:
                        wins += 1
                    elif g < 0:
                        losses += 1
    finally:
        db.close_db(conn)
    wr = (wins / closed * 100) if closed else 0.0
    return {
        "entries": entries,
        "closed": closed,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wr, 1),
        "income": income,
        "block_days": len(block_dates) if block_dates else 0,
    }


def _collect_daily_buys(enabled: list, as_of: date) -> Counter:
    cfg = _make_rci_config()
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    scr = conf.CONF_SEC_SCR
    window = int(conf.get_config(scr, conf.CONF_KEY_SCR_PAST_PERIOD))
    prm = KabInf(
        sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
        past_period=-window,
        srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
        srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
        as_of_date=as_of,
    )
    daily: Counter = Counter()
    conn, cursor = db.connect_db()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for code in enabled:
                if engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor) == -1:
                    continue
                df = prm.outdf
                if df is None or df.empty:
                    continue
                for idx, row in df[df["mark"] == "新買"].iterrows():
                    daily[_row_date(row, idx)] += 1
    finally:
        db.close_db(conn)
    return daily


def main() -> int:
    parser = argparse.ArgumentParser(description="広がりフィルター（RCI停止）バックテスト")
    parser.add_argument("--as-of", action="append", required=True, help="ウィンドウ終了日")
    parser.add_argument(
        "--thresholds",
        default="7,10,15,20,30,50",
        help="新買件数閾値（カンマ区切り）",
    )
    args = parser.parse_args()
    thresholds = [int(x.strip()) for x in args.thresholds.split(",") if x.strip()]
    as_of_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in args.as_of]

    conn, cursor = db.connect_db()
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
    finally:
        db.close_db(conn)

    for as_of in as_of_dates:
        daily = _collect_daily_buys(enabled, as_of)
        peak_day, peak_cnt = daily.most_common(1)[0] if daily else ("-", 0)
        print(f"\n=== {as_of}  window / symbols={len(enabled)} ===")
        print(f"baseline daily buys: max={peak_cnt} on {peak_day}  days_with_buys={len(daily)}")

        base = _run(enabled, as_of, None)
        print(
            f"{'mode':16} {'N':>4} {'block':>5} {'entries':>8} {'closed':>7} "
            f"{'WR':>7} {'income':>12}"
        )
        print(
            f"{'RCI (baseline)':16} {'-':>4} {'-':>5} "
            f"{base['entries']:8} {base['closed']:7} {base['win_rate']:6.1f}% {base['income']:12,}"
        )

        for n in thresholds:
            block = {d for d, c in daily.items() if c >= n}
            r = _run(enabled, as_of, block)
            blocked_entries = base["entries"] - r["entries"]
            print(
                f"{'RCI+breadth':16} {n:4} {len(block):5} "
                f"{r['entries']:8} {r['closed']:7} {r['win_rate']:6.1f}% {r['income']:12,}  "
                f"(entries-{blocked_entries})"
            )

        print("\n[閾値別ブロック日（上位）]")
        for n in thresholds:
            block = {d for d, c in daily.items() if c >= n}
            if not block:
                print(f"  N>={n}: なし")
                continue
            sample = sorted(block)[:5]
            extra = f" ... +{len(block)-5}" if len(block) > 5 else ""
            print(f"  N>={n}: {len(block)}日  例 {sample}{extra}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
