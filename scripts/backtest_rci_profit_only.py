#!/usr/bin/env python3
"""含み益時のみRCI決済 vs 通常RCI決済 vs 現行OFF（全シグナル×100株）."""

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
    ("RCI20/5", 1, 0, "output/optimize/trades_RCI決済7%.json"),
    ("RCI20/5含益", 1, 1, "output/optimize/trades_RCI20_5_profit.json"),
]


def patch(text: str, *, rci_exit: int, profit_only: int) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", f"SCR_JDG_RCI_EXIT = {rci_exit}", text)
    text = re.sub(r"SCR_RCI_EXIT_PROFIT_ONLY\s*=\s*\d+", f"SCR_RCI_EXIT_PROFIT_ONLY = {profit_only}", text)
    if "SCR_RCI_EXIT_PROFIT_ONLY" not in text:
        text = text.replace(
            "SCR_RCI_EXIT_PEAK = 20",
            f"SCR_RCI_EXIT_PEAK = 20\nSCR_RCI_EXIT_PROFIT_ONLY = {profit_only}",
        )
    text = re.sub(r"SCR_RCI_EXIT_PEAK\s*=\s*[\d.]+", "SCR_RCI_EXIT_PEAK = 20", text)
    text = re.sub(r"SCR_RCI_EXIT_TURN_MIN\s*=\s*[\d.]+", "SCR_RCI_EXIT_TURN_MIN = 5", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    text = re.sub(r"SCR_SRSI_HI\s*=\s*\d+", "SCR_SRSI_HI = 60", text)
    text = re.sub(r"SCR_SELL_PERIOD\s*=\s*\d+", "SCR_SELL_PERIOD = 100", text)
    return text


def run(name: str, rci_exit: int, profit_only: int, cache_rel: str) -> dict:
    cache = ROOT / cache_rel
    if cache.is_file():
        trades = json.loads(cache.read_text(encoding="utf-8"))
    else:
        base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
        text = patch(base, rci_exit=rci_exit, profit_only=profit_only)
        tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-rci-profit-"))
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
        stops = sum(1 for t in closed if t.get("exit_reason") == "損切り")
        other = sum(1 for t in closed if t.get("exit_reason") == "その他")
        med = sorted(t["gain"] for t in losses)[len(losses) // 2] if losses else 0
        pf = _calc_pf([{"gain": t["gain"] for t in wins}], [{"gain": t["gain"] for t in losses}])
        return {
            "n": len(closed),
            "win": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "pf": pf,
            "total": sum(t["gain"] for t in closed),
            "stops": stops,
            "other": other,
            "med_loss": med,
            "max_loss": min((t["gain"] for t in closed), default=0),
            "max_gain": max((t["gain"] for t in closed), default=0),
        }

    return {"name": name, "all": stats(ex=set()), "ex2020": stats(ex=EXCLUDE)}


def main() -> int:
    rows = []
    for name, rci, profit, cache in VARIANTS:
        print(f"running {name}...", flush=True)
        rows.append(run(name, rci, profit, cache))

    print("\n=== 含み益RCI決済 比較 ===")
    print(f"{'設定':<12} {'10年':>10} {'2020除':>10} {'PF':>6} {'勝率':>6} {'損切':>5} {'その他':>5} {'負中央':>7}")
    for r in sorted(rows, key=lambda x: -x["ex2020"]["total"]):
        a, x = r["all"], r["ex2020"]
        print(
            f"{r['name']:<12} {a['total']:>+10,} {x['total']:>+10,} {x['pf']:>6} "
            f"{x['win']:>5.1f}% {x['stops']:>5} {x['other']:>5} {x['med_loss']:>+7,}"
        )
    best = max(rows, key=lambda x: x["ex2020"]["total"])
    base = next(r for r in rows if r["name"] == "現行OFF")
    print(f"\n2020除く best: {best['name']} ({best['ex2020']['total']:+,}) vs 現行 ({base['ex2020']['total']:+,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
