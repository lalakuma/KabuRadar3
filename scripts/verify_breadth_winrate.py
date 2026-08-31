#!/usr/bin/env python3
"""エントリー日の広がり(N)別勝率 — コロナ期ウィンドウ除外."""

from __future__ import annotations

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

COVID_END_LO = date(2020, 2, 3)
COVID_END_HI = date(2020, 10, 29)


def _row_date(row, idx) -> date:
    dt = row.get("Index", row.get("datetime", idx))
    if isinstance(dt, datetime):
        return dt.date()
    if isinstance(dt, date):
        return dt
    return datetime.fromisoformat(str(dt)[:10]).date()


def _window_ends(dates: list[date], *, step: int = 60, since: date | None = None) -> list[date]:
    ends: list[date] = []
    i = len(dates) - 1
    while i >= 0:
        end = dates[i]
        if date.fromordinal(end.toordinal() - 100) < dates[0]:
            break
        if since is None or end >= since:
            if not (COVID_END_LO <= end <= COVID_END_HI):
                ends.append(end)
        i -= step
    return sorted(ends)


def _run_window(as_of: date, enabled: list) -> tuple[Counter, list[tuple[date, int]]]:
    text = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp())
    (tmp / "config_lo.ini").write_text(text, encoding="utf-8")
    os.environ["KABURADAR_CONFIG"] = str(tmp / "config_lo.ini")
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
    trades: list[tuple[date, int]] = []
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
                entry: date | None = None
                for idx, row in df.iterrows():
                    mark = str(row.get("mark", ""))
                    if mark == "新買":
                        entry = _row_date(row, idx)
                    elif mark == "返売" and entry is not None:
                        trades.append((entry, int(row["buygain"])))
                        entry = None
    finally:
        db.close_db(conn)
    return daily, trades


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", action="append", help="特定終了日のみ")
    args = parser.parse_args()

    conn, cursor = db.connect_db()
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
        cursor.execute('SELECT datetime FROM "tbl_7203" ORDER BY datetime')
        dates = [datetime.fromisoformat(str(r[0])[:10]).date() for r in cursor.fetchall()]
    finally:
        db.close_db(conn)

    ends = _window_ends(dates, since=date(2018, 1, 1))
    if args.as_of:
        ends = [datetime.strptime(d, "%Y-%m-%d").date() for d in args.as_of]
    buckets: dict[str, list[int]] = {
        "N=7": [0, 0, 0],
        "N>=8": [0, 0, 0],
        "N>=7": [0, 0, 0],
        "N4-6": [0, 0, 0],
        "N<4": [0, 0, 0],
    }

    for as_of in ends:
        daily, trades = _run_window(as_of, enabled)
        for ent, gain in trades:
            n = daily.get(ent, 0)
            keys: list[str] = []
            if n == 7:
                keys.append("N=7")
            if n >= 8:
                keys.append("N>=8")
            if n >= 7:
                keys.append("N>=7")
            elif n >= 4:
                keys.append("N4-6")
            else:
                keys.append("N<4")
            for key in keys:
                if gain > 0:
                    buckets[key][0] += 1
                elif gain < 0:
                    buckets[key][1] += 1
                buckets[key][2] += gain

    print(f"RCI seq / {len(ends)} windows / COVID end dates excluded ({COVID_END_LO}..{COVID_END_HI})")
    print(f"{'bucket':8} {'trades':>7} {'WR':>8} {'income':>14} {'avg':>10}")
    for key in ("N=7", "N>=8", "N>=7", "N4-6", "N<4"):
        wins, losses, income = buckets[key]
        closed = wins + losses
        wr = (wins / closed * 100) if closed else 0.0
        avg = income / closed if closed else 0
        print(f"{key:8} {closed:7} {wr:7.1f}% {income:14,} {avg:10,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
