#!/usr/bin/env python3
"""RSI のみ vs RSI+RCI のエントリー件数・PF を比較する検証スクリプト."""

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


def _make_config(use_rci: bool) -> Path:
    base = ROOT / "config" / "config_lo.ini"
    text = base.read_text(encoding="utf-8")
    if use_rci:
        text = text.replace("SCR_JDG_RCI = 0", "SCR_JDG_RCI = 1")
        if "SCR_JDG_RCI" not in text:
            text = text.replace("SCR_JDG_RSVENT = 0", "SCR_JDG_RSVENT = 0\nSCR_JDG_RCI = 1")
    else:
        text = text.replace("SCR_JDG_RCI = 1", "SCR_JDG_RCI = 0")
        if "SCR_JDG_RCI" not in text:
            text = text.replace("SCR_JDG_RSVENT = 0", "SCR_JDG_RSVENT = 0\nSCR_JDG_RCI = 0")
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-rci-"))
    path = tmp / "config_lo.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _run_variant(use_rci: bool, limit: int | None) -> dict:
    cfg = _make_config(use_rci)
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

        total_entries = 0
        total_wins = 0
        total_losses = 0
        total_income = 0
        plus_gain = 0.0
        minus_gain = 0.0

        for code in enabled:
            ret, _ = engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor)
            if ret == -1:
                continue
            total_entries += prm.entrycnt
            total_wins += prm.win
            total_losses += prm.lose
            total_income += prm.income
            plus_gain += prm.plusgain
            minus_gain += prm.minusgain

        pf = plus_gain / abs(minus_gain) if minus_gain else plus_gain
        win_rate = (total_wins / (total_wins + total_losses) * 100) if (total_wins + total_losses) else 0
        return {
            "variant": "RSI+RCI" if use_rci else "RSI only",
            "symbols": len(enabled),
            "entries": total_entries,
            "wins": total_wins,
            "losses": total_losses,
            "win_rate": round(win_rate, 2),
            "pf": round(float(pf), 3),
            "income": total_income,
        }
    finally:
        db.close_db(conn)
        shutil.rmtree(cfg.parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare RSI-only vs RSI+RCI entry")
    parser.add_argument("--limit", type=int, default=20, help="Max symbols to test")
    args = parser.parse_args()

    a = _run_variant(use_rci=False, limit=args.limit)
    b = _run_variant(use_rci=True, limit=args.limit)

    print("=== verify_rci_entry ===")
    for row in (a, b):
        print(
            f"{row['variant']:8} symbols={row['symbols']} entries={row['entries']} "
            f"win_rate={row['win_rate']}% PF={row['pf']} income={row['income']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
