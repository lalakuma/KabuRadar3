#!/usr/bin/env python3
"""RSI再下抜け閾値グリッド（RSI60保持 + 再下抜け）."""

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

from kaburadar3.analytics.backtest_report import _calc_pf, extract_trades_from_outdf, patch_config_past_period
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf

PAST_DAYS = 3650
EXCLUDE = {"2020"}

LEVELS = [10, 12, 15, 18, 20, 25, 30, 35, 40]


def patch(text: str, *, level: float, rsi10: int = 1, hold: int = 1) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_JDG_RSI10_RECROSS_EXIT\s*=\s*\d+", f"SCR_JDG_RSI10_RECROSS_EXIT = {rsi10}", text)
    text = re.sub(
        r"SCR_RSI_RECROSS_EXIT_LEVEL\s*=\s*[\d.]+",
        f"SCR_RSI_RECROSS_EXIT_LEVEL = {level}",
        text,
    )
    if "SCR_RSI_RECROSS_EXIT_LEVEL" not in text:
        text = text.replace(
            f"SCR_JDG_RSI10_RECROSS_EXIT = {rsi10}",
            f"SCR_JDG_RSI10_RECROSS_EXIT = {rsi10}\nSCR_RSI_RECROSS_EXIT_LEVEL = {level}",
        )
    text = re.sub(r"SCR_RSI60_HOLD_RCI_UP\s*=\s*\d+", f"SCR_RSI60_HOLD_RCI_UP = {hold}", text)
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", "SCR_JDG_RCI_EXIT = 0", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    return text


def run_backtest(level: float, *, hold: int) -> list[dict]:
    if level == 10 and hold == 1:
        cache = ROOT / "output" / "optimize" / "trades_rsi10_1_hold_1.json"
        if cache.is_file():
            return json.loads(cache.read_text(encoding="utf-8"))
    cache = ROOT / "output" / "optimize" / f"trades_hold_recross_{int(level)}.json"
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))

    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch(base, level=level, hold=hold)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-recross-"))
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


def stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in EXCLUDE]
    wins = [t for t in closed if t["gain"] > 0]
    losses = [t for t in closed if t["gain"] < 0]
    wg = sorted(t["gain"] for t in wins)
    lg = sorted(t["gain"] for t in losses)
    pf = _calc_pf([{"gain": t["gain"] for t in wins}], [{"gain": t["gain"] for t in losses}])
    recross = sum(1 for t in closed if t.get("exit_reason") in ("RSI10", "RSI再下抜け"))
    return {
        "total": sum(t["gain"] for t in closed),
        "win": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "pf": pf,
        "recross": recross,
        "stops": sum(1 for t in closed if t.get("exit_reason") == "損切り"),
        "med_w": wg[len(wg) // 2] if wg else 0,
        "med_l": lg[len(lg) // 2] if lg else 0,
    }


def main() -> int:
    rows = []
    hold_only = stats(
        json.loads((ROOT / "output/optimize/trades_RSI60_hold_RCI.json").read_text(encoding="utf-8"))
    )
    rows.append({"name": "保持のみ", "level": "-", **hold_only})

    for level in LEVELS:
        print(f"running 保持+RSI{level}...", flush=True)
        trades = run_backtest(level, hold=1)
        rows.append({"name": f"保持+RSI{level}", "level": level, **stats(trades)})

    print("\n=== RSI再下抜け 閾値グリッド（RSI60保持併用・2020除） ===")
    print(f"{'設定':<14} {'損益':>10} {'PF':>6} {'勝率':>6} {'再下抜':>6} {'損切':>5} {'勝中央':>7} {'負中央':>7}")
    for r in sorted(rows, key=lambda x: -x["total"]):
        print(
            f"{r['name']:<14} {r['total']:>+10,} {r['pf']:>6} {r['win']:>5.1f}% "
            f"{r['recross']:>6} {r['stops']:>5} {r['med_w']:>+7,} {r['med_l']:>+7,}"
        )
    best = max(rows, key=lambda x: x["total"])
    print(f"\nbest: {best['name']} ({best['total']:+,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
