#!/usr/bin/env python3
"""RCI決済パラメータ簡易グリッド（全シグナル×100株）."""

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
    ("現行OFF", 0, 20, 5, "output/optimize/trades_損切7%.json"),
    ("RCI20/5", 1, 20, 5, "output/optimize/trades_RCI決済7%.json"),
    ("RCI30/5", 1, 30, 5, None),
    ("RCI20/8", 1, 20, 8, None),
    ("RCI30/8", 1, 30, 8, None),
    ("RCI25/6", 1, 25, 6, None),
]


def patch(text: str, *, rci_exit: int, peak: float, turn: float) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", f"SCR_JDG_RCI_EXIT = {rci_exit}", text)
    text = re.sub(r"SCR_RCI_EXIT_PEAK\s*=\s*[\d.]+", f"SCR_RCI_EXIT_PEAK = {peak}", text)
    text = re.sub(r"SCR_RCI_EXIT_TURN_MIN\s*=\s*[\d.]+", f"SCR_RCI_EXIT_TURN_MIN = {turn}", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    return text


def run(name: str, rci_exit: int, peak: float, turn: float, cache_rel: str | None) -> dict:
    cache = ROOT / cache_rel if cache_rel else ROOT / "output" / "optimize" / f"trades_RCI{peak}_{turn}.json"
    if cache.is_file() and cache_rel:
        trades = json.loads(cache.read_text(encoding="utf-8"))
    elif cache.is_file() and not cache_rel and cache.name.startswith("trades_RCI"):
        trades = json.loads(cache.read_text(encoding="utf-8"))
    else:
        base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
        text = patch(base, rci_exit=rci_exit, peak=peak, turn=turn)
        tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-rci-grid-"))
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
        if not cache_rel:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")

    def stats(*, ex: set[str]) -> dict:
        closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in ex]
        wins = [t for t in closed if t["gain"] > 0]
        losses = [t for t in closed if t["gain"] < 0]
        stops = [t for t in closed if t.get("exit_reason") == "損切り"]
        other = [t for t in closed if t.get("exit_reason") == "その他"]
        pf = _calc_pf([{"gain": t["gain"] for t in wins}], [{"gain": t["gain"] for t in losses}])
        return {
            "n": len(closed),
            "win": round(len(wins) / len(closed) * 100, 1) if closed else 0,
            "pf": pf,
            "total": sum(t["gain"] for t in closed),
            "stops": len(stops),
            "other": len(other),
            "max_loss": min((t["gain"] for t in closed), default=0),
        }

    s10 = stats(ex=set())
    sx = stats(ex=EXCLUDE)
    return {"name": name, "peak": peak, "turn": turn, "all": s10, "ex2020": sx}


def main() -> int:
    rows = []
    for item in VARIANTS:
        name, rci, peak, turn, cache = item
        print(f"running {name}...", flush=True)
        rows.append(run(name, rci, peak, turn, cache))

    print("\n=== RCI決済パラメータグリッド ===")
    print(f"{'設定':<10} {'10年損益':>10} {'2020除':>10} {'PF':>5} {'勝率':>5} {'損切':>5} {'その他':>5} {'最大損':>8}")
    for r in sorted(rows, key=lambda x: -x["ex2020"]["total"]):
        a, x = r["all"], r["ex2020"]
        print(
            f"{r['name']:<10} {a['total']:>+10,} {x['total']:>+10,} {x['pf']:>5} {x['win']:>4}% "
            f"{x['stops']:>5} {x['other']:>5} {x['max_loss']:>+8,}"
        )
    best = max(rows, key=lambda x: x["ex2020"]["total"])
    base = next(r for r in rows if r["name"] == "現行OFF")
    print(f"\n2020除く best: {best['name']} ({best['ex2020']['total']:+,}) vs 現行 ({base['ex2020']['total']:+,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
