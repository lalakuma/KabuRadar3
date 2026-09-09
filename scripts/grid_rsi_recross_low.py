#!/usr/bin/env python3
"""RSI再下抜け 低閾値（6〜9）検証."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from grid_rsi_recross_level import patch, stats
from kaburadar3.analytics.backtest_report import extract_trades_from_outdf, patch_config_past_period
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf

PAST_DAYS = 3650
LEVELS = [6, 7, 8, 9]


def run_backtest(level: float) -> list[dict]:
    cache = ROOT / "output" / "optimize" / f"trades_hold_recross_{int(level)}.json"
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))

    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch(base, level=level, hold=1)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-recross-lo-"))
    cfg = tmp / "config_lo.ini"
    cfg.write_text(text, encoding="utf-8")
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    conn, cursor = db.connect_db()
    trades: list[dict] = []
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
        scr = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
            past_period=-PAST_DAYS,
            srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
            ent_rest=int(conf.get_config(scr, conf.CONF_KEY_SCR_ENTRY_REST)),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            for code in enabled:
                if engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor) == -1:
                    continue
                trades.extend(extract_trades_from_outdf(str(code), prm.outdf))
    finally:
        db.close_db(conn)
        shutil.rmtree(tmp, ignore_errors=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    return trades


def load(name: str, path: str) -> dict:
    trades = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return {"name": name, **stats(trades)}


def main() -> int:
    rows = [
        load("保持のみ", "output/optimize/trades_RSI60_hold_RCI.json"),
        load("保持+RSI10", "output/optimize/trades_rsi10_1_hold_1.json"),
    ]
    for level in LEVELS:
        print(f"running 保持+RSI{level}...", flush=True)
        rows.append({"name": f"保持+RSI{level}", **stats(run_backtest(level))})

    print("\n=== RSI再下抜け 低閾値（RSI60保持併用・2020除） ===")
    print(f"{'設定':<14} {'損益':>10} {'PF':>6} {'勝率':>6} {'再下抜':>6} {'損切':>5} {'勝中央':>7} {'負中央':>7}")
    base = next(r for r in rows if r["name"] == "保持のみ")
    for r in sorted(rows, key=lambda x: -x["total"]):
        diff = r["total"] - base["total"]
        mark = f" ({diff:+,})" if r["name"] != "保持のみ" else ""
        print(
            f"{r['name']:<14} {r['total']:>+10,} {r['pf']:>6} {r['win']:>5.1f}% "
            f"{r['recross']:>6} {r['stops']:>5} {r['med_w']:>+7,} {r['med_l']:>+7,}{mark}"
        )
    best = max(rows, key=lambda x: x["total"])
    print(f"\nbest: {best['name']} ({best['total']:+,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
