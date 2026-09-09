#!/usr/bin/env python3
"""MA5決済: 当日5日線 vs 前日確定5日線の比較."""

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
CHEAT_CACHE = ROOT / "output" / "optimize" / "ma5_grid" / "offset_m3d00.json"
FIXED_CACHE = ROOT / "output" / "optimize" / "trades_ma5_prev_m3d00.json"


def stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in EXCLUDE]
    wins = [t for t in closed if t["gain"] > 0]
    losses = [t for t in closed if t["gain"] < 0]
    wg = sorted(t["gain"] for t in wins)
    pf = _calc_pf([{"gain": t["gain"] for t in wins}], [{"gain": t["gain"] for t in losses}])
    return {
        "total": sum(t["gain"] for t in closed),
        "win": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "pf": pf,
        "ma5": sum(1 for t in closed if t.get("exit_reason") == "MA5"),
        "rsi60": sum(1 for t in closed if t.get("exit_reason") == "RSI60"),
        "stops": sum(1 for t in closed if t.get("exit_reason") == "損切り"),
        "med_w": wg[len(wg) // 2] if wg else 0,
    }


def run_fixed() -> list[dict]:
    if FIXED_CACHE.is_file():
        return json.loads(FIXED_CACHE.read_text(encoding="utf-8"))
    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch_config_past_period(base, PAST_DAYS)
    text = re.sub(r"SCR_MA5_OFFSET_PCT\s*=\s*[\d.-]+", "SCR_MA5_OFFSET_PCT = -3.0", text)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-ma5-prev-"))
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
    FIXED_CACHE.parent.mkdir(parents=True, exist_ok=True)
    FIXED_CACHE.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    return trades


def main() -> int:
    if not CHEAT_CACHE.is_file():
        print(f"比較元キャッシュなし: {CHEAT_CACHE}")
        return 1
    cheat = stats(json.loads(CHEAT_CACHE.read_text(encoding="utf-8")))
    print("running 前日確定5日線 (offset -3.0%)...", flush=True)
    fixed = stats(run_fixed())
    print("\n=== MA5 offset -3.0% ルックアヘッド検証（2020除） ===")
    print(f"{'':<22} {'勝率':>6} {'損益':>10} {'PF':>6} {'MA5':>5} {'RSI60':>6} {'損切':>5}")
    for label, s in [("当日5日線(旧・疑い)", cheat), ("前日確定5日線(修正)", fixed)]:
        print(
            f"{label:<22} {s['win']:>5.1f}% {s['total']:>+10,} {s['pf']:>6} "
            f"{s['ma5']:>5} {s['rsi60']:>6} {s['stops']:>5}"
        )
    print(f"\n勝率差: {fixed['win'] - cheat['win']:+.1f}pt  損益差: {fixed['total'] - cheat['total']:+,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
