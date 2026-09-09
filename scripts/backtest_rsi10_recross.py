#!/usr/bin/env python3
"""RSI10再下抜け強制決済の検証."""

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

VARIANTS = [
    ("現行OFF", 0, 0, "output/optimize/trades_損切7%.json"),
    ("RSI10再下抜け", 1, 0, None),
    ("RSI60保持", 0, 1, "output/optimize/trades_RSI60_hold_RCI.json"),
    ("保持+RSI10", 1, 1, None),
]


def patch(text: str, *, rsi10: int, hold: int) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_JDG_RSI10_RECROSS_EXIT\s*=\s*\d+", f"SCR_JDG_RSI10_RECROSS_EXIT = {rsi10}", text)
    if "SCR_JDG_RSI10_RECROSS_EXIT" not in text:
        text = text.replace(
            "SCR_JDG_STOP_LOSS = 1",
            f"SCR_JDG_RSI10_RECROSS_EXIT = {rsi10}\nSCR_JDG_STOP_LOSS = 1",
        )
    text = re.sub(r"SCR_RSI60_HOLD_RCI_UP\s*=\s*\d+", f"SCR_RSI60_HOLD_RCI_UP = {hold}", text)
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", "SCR_JDG_RCI_EXIT = 0", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    return text


def run(name: str, rsi10: int, hold: int, cache_rel: str | None) -> dict:
    if cache_rel:
        cache = ROOT / cache_rel
    else:
        tag = f"rsi10_{rsi10}_hold_{hold}"
        cache = ROOT / "output" / "optimize" / f"trades_{tag}.json"
    if cache.is_file() and cache_rel:
        trades = json.loads(cache.read_text(encoding="utf-8"))
    elif cache.is_file() and not cache_rel:
        trades = json.loads(cache.read_text(encoding="utf-8"))
    else:
        base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
        text = patch(base, rsi10=rsi10, hold=hold)
        tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-rsi10-"))
        cfg = tmp / "config_lo.ini"
        cfg.write_text(text, encoding="utf-8")
        os.environ["KABURADAR_CONFIG"] = str(cfg)
        conn, cursor = db.connect_db()
        trades = []
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

    def stats(*, ex: set[str]) -> dict:
        closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in ex]
        wins = [t for t in closed if t["gain"] > 0]
        losses = [t for t in closed if t["gain"] < 0]
        wg = sorted(t["gain"] for t in wins)
        lg = sorted(t["gain"] for t in losses)
        pf = _calc_pf([{"gain": t["gain"] for t in wins}], [{"gain": t["gain"] for t in losses}])
        return {
            "total": sum(t["gain"] for t in closed),
            "win": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "pf": pf,
            "rsi10": sum(1 for t in closed if t.get("exit_reason") == "RSI10"),
            "rsi60": sum(1 for t in closed if t.get("exit_reason") == "RSI60"),
            "other": sum(1 for t in closed if t.get("exit_reason") == "その他"),
            "stops": sum(1 for t in closed if t.get("exit_reason") == "損切り"),
            "med_w": wg[len(wg) // 2] if wg else 0,
            "med_l": lg[len(lg) // 2] if lg else 0,
        }

    return {"name": name, "ex2020": stats(ex=EXCLUDE)}


def main() -> int:
    rows = []
    for name, rsi10, hold, cache in VARIANTS:
        print(f"running {name}...", flush=True)
        rows.append(run(name, rsi10, hold, cache))

    print("\n=== RSI10再下抜け 検証 (2020除) ===")
    print(f"{'設定':<14} {'損益':>10} {'PF':>6} {'勝率':>6} {'RSI10':>6} {'RSI60':>6} {'損切':>5} {'勝中央':>7} {'負中央':>7}")
    for r in sorted(rows, key=lambda x: -x["ex2020"]["total"]):
        x = r["ex2020"]
        print(
            f"{r['name']:<14} {x['total']:>+10,} {x['pf']:>6} {x['win']:>5.1f}% "
            f"{x['rsi10']:>6} {x['rsi60']:>6} {x['stops']:>5} {x['med_w']:>+7,} {x['med_l']:>+7,}"
        )
    best = max(rows, key=lambda x: x["ex2020"]["total"])
    base = next(r for r in rows if r["name"] == "現行OFF")
    print(f"\nbest: {best['name']} ({best['ex2020']['total']:+,}) vs 現行 ({base['ex2020']['total']:+,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
