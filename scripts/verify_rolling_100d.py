#!/usr/bin/env python3
"""複数の100日ウィンドウで RSIのみ vs RSI+RCI を比較."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf

VARIANTS = {
    "RSIのみ": {"SCR_JDG_RCI = 1": "SCR_JDG_RCI = 0", "SCR_JDG_RCI_SEQ = 1": "SCR_JDG_RCI_SEQ = 0"},
    "RSI+RCI": {"SCR_JDG_RCI = 0": "SCR_JDG_RCI = 1", "SCR_JDG_RCI_SEQ = 0": "SCR_JDG_RCI_SEQ = 1"},
}


def _make_config(label: str) -> Path:
    text = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    for k, v in VARIANTS[label].items():
        if k in text:
            text = text.replace(k, v)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-roll-"))
    path = tmp / "config_lo.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _to_date(raw: object) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    return datetime.fromisoformat(str(raw)[:10]).date()


def _trading_dates(cursor, code: str = "7203") -> list[date]:
    cursor.execute(f'SELECT datetime FROM "tbl_{code}" ORDER BY datetime')
    return [_to_date(row[0]) for row in cursor.fetchall()]


def _window_ends(dates: list[date], *, step: int, window_days: int, since: date | None) -> list[date]:
    if not dates:
        return []
    earliest = dates[0]
    ends: list[date] = []
    i = len(dates) - 1
    while i >= 0:
        end = dates[i]
        if date.fromordinal(end.toordinal() - window_days) < earliest:
            break
        if since is None or end >= since:
            ends.append(end)
        j = i - step
        i = j
    return sorted(ends)


def _run_window(cfg: Path, as_of: date, enabled: list) -> dict:
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    conn, cursor = db.connect_db()
    try:
        scr = conf.CONF_SEC_SCR
        window = int(conf.get_config(scr, conf.CONF_KEY_SCR_PAST_PERIOD))
        prm = KabInf(
            sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
            past_period=-window,
            srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
            as_of_date=as_of,
        )
        entries = wins = losses = income = 0
        plus_gain = minus_gain = 0.0
        max_loss = 0
        max_loss_trade = ""
        with contextlib.redirect_stdout(io.StringIO()):
            for code in enabled:
                result = engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor)
                if result == -1:
                    continue
                entries += prm.entrycnt
                wins += prm.win
                losses += prm.lose
                income += prm.income
                plus_gain += prm.plusgain
                minus_gain += prm.minusgain
                outdf = prm.outdf
                if outdf is None or outdf.empty or "buygain" not in outdf.columns:
                    continue
                for idx, row in outdf.loc[outdf["buygain"] < 0].iterrows():
                    gain = int(row["buygain"])
                    if gain >= max_loss:
                        continue
                    max_loss = gain
                    dt = row.get("Index", row.get("datetime", idx))
                    if hasattr(dt, "date"):
                        dt = dt.date()
                    max_loss_trade = f"{code}@{dt}"
        closed = wins + losses
        pf = plus_gain / abs(minus_gain) if minus_gain else plus_gain
        wr = (wins / closed * 100) if closed else 0.0
        return {
            "entries": entries,
            "closed": closed,
            "win_rate": round(wr, 1),
            "pf": round(float(pf), 2),
            "income": income,
            "max_loss": max_loss,
            "max_loss_trade": max_loss_trade,
        }
    finally:
        db.close_db(conn)


def _summarize(rows: list[dict], key: str) -> str:
    vals = [r[key] for r in rows]
    if not vals:
        return "-"
    if key == "win_rate":
        return f"avg={sum(vals)/len(vals):.1f}% min={min(vals):.1f}% max={max(vals):.1f}%"
    if key == "pf":
        return f"avg={sum(vals)/len(vals):.2f} min={min(vals):.2f} max={max(vals):.2f}"
    if key == "entries":
        return f"avg={sum(vals)/len(vals):.1f} min={min(vals)} max={max(vals)}"
    total = sum(vals)
    return f"sum={total:,} avg={total/len(vals):,.0f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Rolling 100-day RSI vs RSI+RCI comparison")
    parser.add_argument("--step", type=int, default=60, help="ウィンドウ終了日の間隔（営業日）")
    parser.add_argument("--since", default="2018-01-01", help="この日以降の終了日のみ")
    parser.add_argument("--limit-windows", type=int, default=0, help="最大ウィンドウ数（0=全件）")
    args = parser.parse_args()
    since = datetime.strptime(args.since, "%Y-%m-%d").date()
    window_days = int(
        (ROOT / "config" / "config_lo.ini")
        .read_text(encoding="utf-8")
        .split("SCR_PAST_PERIOD = ")[1]
        .split()[0]
    )

    conn, cursor = db.connect_db()
    try:
        dates = _trading_dates(cursor)
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
    finally:
        db.close_db(conn)

    ends = _window_ends(dates, step=args.step, window_days=window_days, since=since)
    if args.limit_windows:
        ends = ends[-args.limit_windows :]

    cfg_rsi = _make_config("RSIのみ")
    cfg_rci = _make_config("RSI+RCI")
    results: list[dict] = []

    print(f"=== rolling {window_days}day windows / step={args.step}営業日 / since={since} ===")
    print(f"windows={len(ends)} symbols={len(enabled)}")
    print(
        f"{'end':12} {'RSI ent':>7} {'RSI WR':>7} {'RSI PF':>7} {'RSI maxL':>8} "
        f"{'RCI ent':>7} {'RCI WR':>7} {'RCI PF':>7} {'RCI maxL':>8} {'RCI-RSI income':>14}"
    )

    for end in ends:
        rsi = _run_window(cfg_rsi, end, enabled)
        rci = _run_window(cfg_rci, end, enabled)
        results.append({"end": end, "rsi": rsi, "rci": rci})
        diff = rci["income"] - rsi["income"]
        print(
            f"{end.isoformat():12} {rsi['entries']:7} {rsi['win_rate']:6.1f}% {rsi['pf']:7.2f} "
            f"{rsi['max_loss']:8,} {rci['entries']:7} {rci['win_rate']:6.1f}% {rci['pf']:7.2f} "
            f"{rci['max_loss']:8,} {diff:14,}",
            flush=True,
        )
        if rsi["max_loss_trade"] or rci["max_loss_trade"]:
            print(
                f"  worst RSI: {rsi['max_loss_trade'] or '-'}  "
                f"worst RCI: {rci['max_loss_trade'] or '-'}",
                flush=True,
            )

    shutil.rmtree(cfg_rsi.parent, ignore_errors=True)
    shutil.rmtree(cfg_rci.parent, ignore_errors=True)

    rsi_rows = [r["rsi"] for r in results]
    rci_rows = [r["rci"] for r in results]
    n = len(results)
    rci_wins_wr = sum(1 for r in results if r["rci"]["win_rate"] > r["rsi"]["win_rate"])
    rci_wins_pf = sum(1 for r in results if r["rci"]["pf"] > r["rsi"]["pf"])
    rci_wins_inc = sum(1 for r in results if r["rci"]["income"] > r["rsi"]["income"])

    print()
    print("--- 集計 ---")
    print(
        f"RSIのみ  entries {_summarize(rsi_rows, 'entries')}  WR {_summarize(rsi_rows, 'win_rate')}  "
        f"PF {_summarize(rsi_rows, 'pf')}  income {_summarize(rsi_rows, 'income')}"
    )
    print(
        f"RSI+RCI  entries {_summarize(rci_rows, 'entries')}  WR {_summarize(rci_rows, 'win_rate')}  "
        f"PF {_summarize(rci_rows, 'pf')}  income {_summarize(rci_rows, 'income')}"
    )
    print(f"RCI が優勢: 勝率 {rci_wins_wr}/{n}  PF {rci_wins_pf}/{n}  損益 {rci_wins_inc}/{n}")
    rsi_max_losses = [r["max_loss"] for r in rsi_rows if r["max_loss"] < 0]
    rci_max_losses = [r["max_loss"] for r in rci_rows if r["max_loss"] < 0]
    if rsi_max_losses:
        print(
            f"1取引最大損失(RSI)  avg={sum(rsi_max_losses)/len(rsi_max_losses):,.0f}  "
            f"worst={min(rsi_max_losses):,}"
        )
    if rci_max_losses:
        print(
            f"1取引最大損失(RCI)  avg={sum(rci_max_losses)/len(rci_max_losses):,.0f}  "
            f"worst={min(rci_max_losses):,}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
