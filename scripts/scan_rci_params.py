#!/usr/bin/env python3
"""RCI パラメータと勝率・PF の関係をスキャン（RSI準備→RCI上向きエントリー）."""

from __future__ import annotations

import os
import re
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


def _base_text() -> str:
    return (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")


def _make_config(**overrides: str) -> Path:
    text = _base_text()
    for key, val in overrides.items():
        text = re.sub(rf"^{re.escape(key)}\s*=.*$", f"{key} = {val}", text, flags=re.M)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-rci-scan-"))
    path = tmp / "config_lo.ini"
    path.write_text(text, encoding="utf-8")
    return path


def _run(cfg: Path) -> dict:
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    conn, cursor = db.connect_db()
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
        scr = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
            past_period=-int(conf.get_config(scr, conf.CONF_KEY_SCR_PAST_PERIOD)),
            srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
        )
        entries = wins = losses = income = 0
        plus_gain = minus_gain = 0.0
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
        closed = wins + losses
        pf = plus_gain / abs(minus_gain) if minus_gain else plus_gain
        wr = (wins / closed * 100) if closed else 0
        return {"entries": entries, "closed": closed, "win_rate": round(wr, 1), "pf": round(float(pf), 2), "income": income}
    finally:
        db.close_db(conn)
        shutil.rmtree(cfg.parent, ignore_errors=True)


def main() -> int:
    grid = [
        ("現設定 turn=1 prep=30", {"SCR_RCI_TURN_MIN": "1", "SCR_RCI_PREP_MAX_BARS": "30", "SCR_RCI_PERIOD": "9"}),
        ("turn=0 prep=30", {"SCR_RCI_TURN_MIN": "0", "SCR_RCI_PREP_MAX_BARS": "30", "SCR_RCI_PERIOD": "9"}),
        ("turn=3 prep=30", {"SCR_RCI_TURN_MIN": "3", "SCR_RCI_PREP_MAX_BARS": "30", "SCR_RCI_PERIOD": "9"}),
        ("turn=5 prep=30", {"SCR_RCI_TURN_MIN": "5", "SCR_RCI_PREP_MAX_BARS": "30", "SCR_RCI_PERIOD": "9"}),
        ("turn=1 prep=20", {"SCR_RCI_TURN_MIN": "1", "SCR_RCI_PREP_MAX_BARS": "20", "SCR_RCI_PERIOD": "9"}),
        ("turn=1 prep=40", {"SCR_RCI_TURN_MIN": "1", "SCR_RCI_PREP_MAX_BARS": "40", "SCR_RCI_PERIOD": "9"}),
        ("period=6 turn=1", {"SCR_RCI_TURN_MIN": "1", "SCR_RCI_PREP_MAX_BARS": "30", "SCR_RCI_PERIOD": "6"}),
        ("period=12 turn=1", {"SCR_RCI_TURN_MIN": "1", "SCR_RCI_PREP_MAX_BARS": "30", "SCR_RCI_PERIOD": "12"}),
        ("period=26 turn=1", {"SCR_RCI_TURN_MIN": "1", "SCR_RCI_PREP_MAX_BARS": "30", "SCR_RCI_PERIOD": "26"}),
    ]

    print("=== RCI param scan (397銘柄 / 100日 / RSI準備→RCI上向き) ===")
    print(f"{'label':22} {'ent':>4} {'cls':>4} {'WR%':>6} {'PF':>5} {'income':>8}")
    rows = []
    for label, ov in grid:
        r = _run(_make_config(**ov))
        rows.append((label, r))
        print(f"{label:22} {r['entries']:4} {r['closed']:4} {r['win_rate']:6} {r['pf']:5} {r['income']:8}")

    best_wr = max(rows, key=lambda x: (x[1]["win_rate"], x[1]["pf"]))
    best_pf = max(rows, key=lambda x: (x[1]["pf"], x[1]["win_rate"]))
    print()
    print(f"最高勝率: {best_wr[0]} → WR {best_wr[1]['win_rate']}% PF {best_wr[1]['pf']}")
    print(f"最高PF:   {best_pf[0]} → WR {best_pf[1]['win_rate']}% PF {best_pf[1]['pf']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
