#!/usr/bin/env python3
"""旧決済 vs 改善決済（RCI反転・損切り・短保有）のバックテスト比較."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf

BASELINE_OVERRIDES = {
    "SCR_JDG_RCI_EXIT = 1": "SCR_JDG_RCI_EXIT = 0",
    "SCR_JDG_STOP_LOSS = 1": "SCR_JDG_STOP_LOSS = 0",
    "SCR_SRSI_HI = 35": "SCR_SRSI_HI = 60",
    "SCR_SELL_PERIOD = 20": "SCR_SELL_PERIOD = 100",
}


def _make_config(baseline: bool) -> Path:
    text = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    if baseline:
        for new, old in BASELINE_OVERRIDES.items():
            text = text.replace(new, old)
        # 旧設定にキーが無い場合のフォールバック
        if "SCR_JDG_RCI_EXIT" not in text:
            text = text.replace(
                "SCR_RCI_LOOKBACK = 5",
                "SCR_RCI_LOOKBACK = 5\nSCR_JDG_RCI_EXIT = 0\nSCR_JDG_STOP_LOSS = 0",
            )
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-exit-"))
    path = tmp / "config_lo.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _run_backtest(cfg: Path, limit: int | None) -> dict:
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    conn, cursor = db.connect_db()
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
        if limit:
            enabled = enabled[:limit]

        scrsec = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SELL_PERIOD)),
            past_period=-int(conf.get_config(scrsec, conf.CONF_KEY_SCR_PAST_PERIOD)),
            srsi_hi=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_LOW)),
            ent_rest=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_ENTRY_REST)),
        )

        written = 0
        skipped = 0
        total_entries = 0
        total_wins = 0
        total_losses = 0
        total_income = 0
        plus_gain = 0.0
        minus_gain = 0.0

        for code in enabled:
            result = engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor)
            if result == -1:
                skipped += 1
                continue
            if prm.outcodecsv:
                written += 1
            total_entries += prm.entrycnt
            total_wins += prm.win
            total_losses += prm.lose
            total_income += prm.income
            plus_gain += prm.plusgain
            minus_gain += prm.minusgain

        pf = plus_gain / abs(minus_gain) if minus_gain else plus_gain
        win_rate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) else 0
        return {
            "symbols": len(enabled),
            "written": written,
            "skipped": skipped,
            "entries": total_entries,
            "closed": total_wins + total_losses,
            "wins": total_wins,
            "losses": total_losses,
            "win_rate": round(win_rate, 2),
            "pf": round(float(pf), 3),
            "income": total_income,
        }
    finally:
        db.close_db(conn)
        shutil.rmtree(cfg.parent, ignore_errors=True)


def _run_single_code(code: str, baseline: bool) -> dict:
    cfg = _make_config(baseline)
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    conn, cursor = db.connect_db()
    try:
        scrsec = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SELL_PERIOD)),
            past_period=-int(conf.get_config(scrsec, conf.CONF_KEY_SCR_PAST_PERIOD)),
            srsi_hi=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_LOW)),
        )
        engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor)
        df = prm.outdf
        marks = df[df["mark"].isin(["新買", "返売", "継続"])][["mark", "close"]].tail(10)
        return {
            "code": code,
            "entries": prm.entrycnt,
            "wins": prm.win,
            "losses": prm.lose,
            "income": prm.income,
            "tail": marks.to_string(),
        }
    finally:
        db.close_db(conn)
        shutil.rmtree(cfg.parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline vs improved exit rules")
    parser.add_argument("--limit", type=int, default=None, help="Max symbols (default: all)")
    args = parser.parse_args()

    old = _run_backtest(_make_config(baseline=True), args.limit)
    new = _run_backtest(_make_config(baseline=False), args.limit)
    s7649_old = _run_single_code("7649", baseline=True)
    s7649_new = _run_single_code("7649", baseline=False)

    print("=== verify_exit_improvements (LO / 100日) ===")
    print(
        f"{'baseline':10} written={old['written']:3} closed={old['closed']:3} "
        f"entries={old['entries']:3} win_rate={old['win_rate']:5}% PF={old['pf']} income={old['income']}"
    )
    print(
        f"{'improved':10} written={new['written']:3} closed={new['closed']:3} "
        f"entries={new['entries']:3} win_rate={new['win_rate']:5}% PF={new['pf']} income={new['income']}"
    )
    print()
    print("=== 7649 スギHD ===")
    print(f"baseline: entries={s7649_old['entries']} W/L={s7649_old['wins']}/{s7649_old['losses']} income={s7649_old['income']}")
    print(f"improved: entries={s7649_new['entries']} W/L={s7649_new['wins']}/{s7649_new['losses']} income={s7649_new['income']}")
    if s7649_new["tail"]:
        print(s7649_new["tail"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
