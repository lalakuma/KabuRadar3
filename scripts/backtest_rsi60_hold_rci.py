#!/usr/bin/env python3
"""RSI60超え後もRCI上向きなら保持 vs 現行."""

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
CACHE = ROOT / "output" / "optimize" / "trades_RSI60_hold_RCI.json"
BASE = ROOT / "output" / "optimize" / "trades_損切7%.json"


def patch(text: str, *, hold: int) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_RSI60_HOLD_RCI_UP\s*=\s*\d+", f"SCR_RSI60_HOLD_RCI_UP = {hold}", text)
    if "SCR_RSI60_HOLD_RCI_UP" not in text:
        text = text.replace("SCR_JDG_RCI_EXIT = 0", f"SCR_JDG_RCI_EXIT = 0\nSCR_RSI60_HOLD_RCI_UP = {hold}")
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", "SCR_JDG_RCI_EXIT = 0", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    return text


def run_backtest(*, hold: int) -> list[dict]:
    cache = CACHE if hold else BASE
    if hold and cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    if not hold and cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))

    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch(base, hold=hold)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-rsi60-hold-"))
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
    if hold:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    return trades


def stats(trades: list[dict], ex: set[str]) -> dict:
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in ex]
    wins = sorted(t["gain"] for t in closed if t["gain"] > 0)
    losses = sorted(t["gain"] for t in closed if t["gain"] < 0)
    med = lambda a: a[len(a) // 2] if a else 0
    pf = _calc_pf(
        [{"gain": g} for g in wins],
        [{"gain": g} for g in losses],
    )
    return {
        "total": sum(t["gain"] for t in closed),
        "win_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "pf": pf,
        "rsi60": sum(1 for t in closed if t.get("exit_reason") == "RSI60"),
        "other": sum(1 for t in closed if t.get("exit_reason") == "その他"),
        "stops": sum(1 for t in closed if t.get("exit_reason") == "損切り"),
        "med_w": med(wins),
        "med_l": med(losses),
        "max_g": max((t["gain"] for t in closed), default=0),
        "avg_hold_w": round(sum(t["hold_days"] for t in closed if t["gain"] > 0) / len(wins), 1) if wins else 0,
    }


def main() -> int:
    print("running 現行OFF...", flush=True)
    base = run_backtest(hold=0)
    print("running RSI60+RCI保持...", flush=True)
    hold = run_backtest(hold=1)
    print("\n=== RSI60超え後RCI上向き保持 ===")
    print(f"{'設定':<16} {'2020除':>10} {'PF':>6} {'勝率':>6} {'RSI60':>6} {'その他':>5} {'勝中央':>7} {'負中央':>7} {'最大益':>8} {'勝保有':>6}")
    for label, trades in [("現行(RSI60即)", base), ("RSI60+RCI保持", hold)]:
        x = stats(trades, EXCLUDE)
        print(
            f"{label:<16} {x['total']:>+10,} {x['pf']:>6} {x['win_pct']:>5.1f}% "
            f"{x['rsi60']:>6} {x['other']:>5} {x['med_w']:>+7,} {x['med_l']:>+7,} "
            f"{x['max_g']:>+8,} {x['avg_hold_w']:>5.1f}日"
        )
    b, h = stats(base, EXCLUDE), stats(hold, EXCLUDE)
    print(f"\n差(保持-現行): {h['total']-b['total']:+,}  勝中央:{h['med_w']-b['med_w']:+,}  最大益:{h['max_g']-b['max_g']:+,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
