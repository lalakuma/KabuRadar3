#!/usr/bin/env python3
"""エントリー条件の緩和案を比較（決済: RSI60 + 損切り3%）."""

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

# 決済は共通: RSI60 / 損切り3% / RCI決済OFF / 保有100日
EXIT_BASE = """
SCR_SRSI_HI = 60
SCR_SELL_PERIOD = 100
SCR_JDG_RCI_EXIT = 0
SCR_JDG_STOP_LOSS = 1
SCR_STOP_LOSS_PCT = 3.0
"""

VARIANTS = {
    "A_RCI厳格(現状)": {
        "SCR_JDG_RCI = 1": "SCR_JDG_RCI = 1",
        "SCR_JDG_RCI_SEQ = 1": "SCR_JDG_RCI_SEQ = 0",
        "SCR_RCI_LOW = -60": "SCR_RCI_LOW = -80",
        "SCR_RCI_TURN_MIN = 3": "SCR_RCI_TURN_MIN = 5",
    },
    "B_RCI緩和": {
        "SCR_JDG_RCI = 1": "SCR_JDG_RCI = 1",
        "SCR_JDG_RCI_SEQ = 1": "SCR_JDG_RCI_SEQ = 0",
    },
    "C_RSIのみ": {
        "SCR_JDG_RCI = 1": "SCR_JDG_RCI = 0",
        "SCR_JDG_RCI_SEQ = 1": "SCR_JDG_RCI_SEQ = 0",
    },
    "D_RSI準備+RCI": {
        "SCR_JDG_RCI = 0": "SCR_JDG_RCI = 1",
        "SCR_JDG_RCI_SEQ = 0": "SCR_JDG_RCI_SEQ = 1",
    },
}


def _make_config(label: str, overrides: dict) -> Path:
    text = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    for k, v in overrides.items():
        if k in text:
            text = text.replace(k, v)
        elif "SCR_JDG_RCI = 0" in text and k == "SCR_JDG_RCI = 1":
            text = text.replace("SCR_JDG_RCI = 0", v)
    for line in EXIT_BASE.strip().splitlines():
        key = line.split("=")[0].strip()
        text = re.sub(rf"^{re.escape(key)}\s*=.*$", line.strip(), text, flags=re.M)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-entry-"))
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
        scrsec = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SELL_PERIOD)),
            past_period=-int(conf.get_config(scrsec, conf.CONF_KEY_SCR_PAST_PERIOD)),
            srsi_hi=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_LOW)),
        )
        written = skipped = entries = wins = losses = income = 0
        plus_gain = minus_gain = 0.0
        for code in enabled:
            result = engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor)
            if result == -1:
                skipped += 1
                continue
            if prm.outcodecsv:
                written += 1
            entries += prm.entrycnt
            wins += prm.win
            losses += prm.lose
            income += prm.income
            plus_gain += prm.plusgain
            minus_gain += prm.minusgain
        closed = wins + losses
        pf = plus_gain / abs(minus_gain) if minus_gain else plus_gain
        wr = (wins / closed * 100) if closed else 0
        return {
            "written": written,
            "skipped": skipped,
            "entries": entries,
            "closed": closed,
            "win_rate": round(wr, 1),
            "pf": round(float(pf), 2),
            "income": income,
        }
    finally:
        db.close_db(conn)
        shutil.rmtree(cfg.parent, ignore_errors=True)


def main() -> int:
    print("=== entry variants (exit: RSI60 + stop -3%) ===")
    for label, ov in VARIANTS.items():
        r = _run(_make_config(label, ov))
        print(
            f"{label:14} written={r['written']:3} entries={r['entries']:4} "
            f"closed={r['closed']:4} WR={r['win_rate']:5}% PF={r['pf']:5} income={r['income']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
