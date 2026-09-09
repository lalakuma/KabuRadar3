#!/usr/bin/env python3
"""5日線接近利確 vs 現行（RSI60+RCI保持）の比較."""

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
CACHE = ROOT / "output" / "optimize" / "trades_ma5_exit.json"
BASE = ROOT / "output" / "optimize" / "trades_RSI60_hold_RCI.json"


def patch(text: str, *, ma5: int) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_JDG_MA5_EXIT\s*=\s*\d+", f"SCR_JDG_MA5_EXIT = {ma5}", text)
    if "SCR_JDG_MA5_EXIT" not in text:
        text = text.replace(
            "SCR_JDG_STOP_LOSS = 1",
            f"SCR_JDG_MA5_EXIT = {ma5}\nSCR_MA5_PROXIMITY_PCT = 1.5\n"
            f"SCR_MA5_RALLY_PCT = 1.0\nSCR_MA5_MIN_BARS = 1\nSCR_MA5_PROFIT_ONLY = 1\n"
            "SCR_JDG_STOP_LOSS = 1",
        )
    text = re.sub(r"SCR_RSI60_HOLD_RCI_UP\s*=\s*\d+", "SCR_RSI60_HOLD_RCI_UP = 1", text)
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", "SCR_JDG_RCI_EXIT = 0", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    return text


def stats(trades: list[dict], ex: set[str]) -> dict:
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in ex]
    wins = sorted(t["gain"] for t in closed if t["gain"] > 0)
    losses = sorted(t["gain"] for t in closed if t["gain"] < 0)
    med = lambda a: a[len(a) // 2] if a else 0
    pf = _calc_pf([{"gain": g} for g in wins], [{"gain": g} for g in losses])
    return {
        "total": sum(t["gain"] for t in closed),
        "win_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "pf": pf,
        "ma5": sum(1 for t in closed if t.get("exit_reason") == "MA5"),
        "rsi60": sum(1 for t in closed if t.get("exit_reason") == "RSI60"),
        "stops": sum(1 for t in closed if t.get("exit_reason") == "損切り"),
        "med_w": med(wins),
        "med_l": med(losses),
        "avg_hold_w": round(sum(t["hold_days"] for t in closed if t["gain"] > 0) / len(wins), 1) if wins else 0,
    }


def run_backtest(*, ma5: int) -> list[dict]:
    cache = CACHE if ma5 else BASE
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))

    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch(base, ma5=ma5)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-ma5-"))
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
    if ma5:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    return trades


def main() -> int:
    print("running 現行...", flush=True)
    base = run_backtest(ma5=0)
    print("running +MA5接近利確...", flush=True)
    ma5 = run_backtest(ma5=1)
    print("\n=== 5日線接近利確 比較（約10年・2020除） ===")
    print(f"{'設定':<18} {'2020除':>10} {'PF':>6} {'勝率':>6} {'MA5':>5} {'RSI60':>6} {'損切':>5} {'勝中央':>7} {'勝保有':>6}")
    for label, trades in [("現行(RSI60+RCI)", base), ("+MA5接近利確", ma5)]:
        x = stats(trades, EXCLUDE)
        print(
            f"{label:<18} {x['total']:>+10,} {x['pf']:>6} {x['win_pct']:>5.1f}% "
            f"{x['ma5']:>5} {x['rsi60']:>6} {x['stops']:>5} {x['med_w']:>+7,} {x['avg_hold_w']:>5.1f}日"
        )
    b, m = stats(base, EXCLUDE), stats(ma5, EXCLUDE)
    print(f"\n差(MA5-現行): {m['total']-b['total']:+,}  勝率:{m['win_pct']-b['win_pct']:+.1f}pt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
