#!/usr/bin/env python3
"""指定終了日の100日ウィンドウを RSIのみ / RSI+RCI で詳細分析."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
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
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-detail-"))
    path = tmp / "config_lo.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _row_date(row, idx) -> date:
    dt = row.get("Index", row.get("datetime", idx))
    if isinstance(dt, datetime):
        return dt.date()
    if isinstance(dt, date):
        return dt
    return datetime.fromisoformat(str(dt)[:10]).date()


def _infer_exit_reason(buy_price: float, exit_row, hold_days: int, stop_pct: float, sell_period: int) -> str:
    exit_close = float(exit_row["close"])
    pct = (exit_close - buy_price) / buy_price * 100.0 if buy_price else 0.0
    rsi4 = float(exit_row.get("RSI4", 0) or 0)
    if pct <= -stop_pct + 0.05:
        return "損切り"
    if hold_days >= sell_period:
        return "100日"
    if rsi4 > 60:
        return "RSI60"
    return "その他"


def _extract_trades(code: str, outdf) -> list[dict]:
    if outdf is None or outdf.empty:
        return []
    stop_pct = float(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_STOP_LOSS_PCT, default="3"))
    sell_period = int(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_SELL_PERIOD))
    trades: list[dict] = []
    entry_date = None
    buy_price = 0.0
    hold_days = 0
    for idx, row in outdf.iterrows():
        mark = str(row.get("mark", ""))
        if mark == "新買":
            entry_date = _row_date(row, idx)
            buy_price = float(row["close"])
            hold_days = 0
        elif mark == "継続" and entry_date is not None:
            hold_days += 1
        elif mark == "返売" and entry_date is not None:
            hold_days += 1
            gain = int(row["buygain"])
            exit_date = _row_date(row, idx)
            trades.append(
                {
                    "code": code,
                    "entry": entry_date,
                    "exit": exit_date,
                    "buy_price": int(buy_price),
                    "exit_price": int(row["close"]),
                    "gain": gain,
                    "hold_days": hold_days,
                    "exit_reason": _infer_exit_reason(buy_price, row, hold_days, stop_pct, sell_period),
                }
            )
            entry_date = None
            buy_price = 0.0
            hold_days = 0
    return trades


def _analyze(label: str, as_of: date, enabled: list) -> tuple[list[dict], Path]:
    cfg = _make_config(label)
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
    all_trades: list[dict] = []
    conn, cursor = db.connect_db()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            for code in enabled:
                if engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor) == -1:
                    continue
                for t in _extract_trades(str(code), prm.outdf):
                    all_trades.append(t)
    finally:
        db.close_db(conn)
    return all_trades, cfg.parent


def _print_summary(label: str, trades: list[dict]) -> None:
    closed = [t for t in trades if t["gain"] != 0]
    wins = [t for t in closed if t["gain"] > 0]
    losses = [t for t in closed if t["gain"] < 0]
    income = sum(t["gain"] for t in closed)
    plus = sum(t["gain"] for t in wins)
    minus = sum(t["gain"] for t in losses)
    pf = plus / abs(minus) if minus else plus
    wr = len(wins) / len(closed) * 100 if closed else 0
    entries = len({(t["code"], t["entry"]) for t in trades})

    print(f"\n=== {label} ===")
    print(f"エントリー: {entries}  決済: {len(closed)}  勝: {len(wins)}  負: {len(losses)}")
    print(f"勝率: {wr:.1f}%  PF: {pf:.2f}  損益: {income:,}円")
    print(f"総利益: {plus:,}  総損失: {minus:,}")
    if closed:
        print(f"1取引平均: {income/len(closed):,.0f}円  最大利益: {max(t['gain'] for t in closed):,}  最大損失: {min(t['gain'] for t in closed):,}")

    by_month = Counter(t["entry"].strftime("%Y-%m") for t in trades)
    print("\n[エントリー月別]")
    for m in sorted(by_month):
        print(f"  {m}: {by_month[m]}件")

    by_exit = Counter(t["exit_reason"] for t in closed)
    print("\n[決済理由（推定）]")
    for k in ("損切り", "RSI60", "100日", "その他"):
        if by_exit[k]:
            sub = [t for t in closed if t["exit_reason"] == k]
            sub_inc = sum(t["gain"] for t in sub)
            print(f"  {k}: {by_exit[k]}件  損益{sub_inc:,}円")

    print("\n[最大損失 TOP10]")
    for t in sorted(closed, key=lambda x: x["gain"])[:10]:
        print(
            f"  {t['code']} {t['entry']}->{t['exit']} "
            f"{t['buy_price']:,}->{t['exit_price']:,} {t['gain']:,} "
            f"({t['hold_days']}d/{t['exit_reason']})"
        )

    print("\n[最大利益 TOP5]")
    for t in sorted(closed, key=lambda x: x["gain"], reverse=True)[:5]:
        print(
            f"  {t['code']} {t['entry']}->{t['exit']} "
            f"{t['buy_price']:,}->{t['exit_price']:,} {t['gain']:,} "
            f"({t['hold_days']}d/{t['exit_reason']})"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True, help="ウィンドウ終了日 YYYY-MM-DD")
    args = parser.parse_args()
    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()

    conn, cursor = db.connect_db()
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
        cursor.execute('SELECT datetime FROM "tbl_7203" ORDER BY datetime')
        dates = [datetime.fromisoformat(str(r[0])[:10]).date() for r in cursor.fetchall()]
    finally:
        db.close_db(conn)

    idx = dates.index(as_of) if as_of in dates else -1
    if idx >= 100:
        start = dates[idx - 100]
        print(f"ウィンドウ: {start} 〜 {as_of}（100営業日）  銘柄数: {len(enabled)}")
    else:
        print(f"終了日: {as_of}  銘柄数: {len(enabled)}")

    cfgs: list[Path] = []
    rsi_trades = rci_trades = None
    for label in ("RSIのみ", "RSI+RCI"):
        trades, cfg_dir = _analyze(label, as_of, enabled)
        cfgs.append(cfg_dir)
        if label == "RSIのみ":
            rsi_trades = trades
        else:
            rci_trades = trades
        _print_summary(label, trades)

    assert rsi_trades is not None and rci_trades is not None
    rsi_codes = {(t["code"], t["entry"]) for t in rsi_trades}
    rci_codes = {(t["code"], t["entry"]) for t in rci_trades}
    only_rsi = rsi_codes - rci_codes
    only_rci = rci_codes - rsi_codes
    both = rsi_codes & rci_codes
    print("\n=== RSI vs RCI エントリー差 ===")
    print(f"両方: {len(both)}  RSIのみ: {len(only_rsi)}  RCIのみ: {len(only_rci)}")
    rsi_inc = sum(t["gain"] for t in rsi_trades)
    rci_inc = sum(t["gain"] for t in rci_trades)
    print(f"損益差 (RCI-RSI): {rci_inc - rsi_inc:,}円")

    for d in cfgs:
        shutil.rmtree(d, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
