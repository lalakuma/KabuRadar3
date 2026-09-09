#!/usr/bin/env python3
"""RCI下向き決済ON vs 現行(損切7%・RCI決済OFF) 全シグナル×100株."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.backtest_report import _calc_pf, extract_trades_from_outdf, patch_config_past_period
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf

PAST_DAYS = 3650
OUT = ROOT / "output" / "optimize" / "trades_RCI決済7%.json"
BASE = ROOT / "output" / "optimize" / "trades_損切7%.json"


def patch_config(text: str, *, rci_exit: bool) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    val = 1 if rci_exit else 0
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", f"SCR_JDG_RCI_EXIT = {val}", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    text = re.sub(r"SCR_SRSI_HI\s*=\s*\d+", "SCR_SRSI_HI = 60", text)
    text = re.sub(r"SCR_SELL_PERIOD\s*=\s*\d+", "SCR_SELL_PERIOD = 100", text)
    return text


def run_backtest(*, rci_exit: bool, cache: Path) -> list[dict]:
    if cache.is_file() and cache != BASE:
        return json.loads(cache.read_text(encoding="utf-8"))

    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch_config(base, rci_exit=rci_exit)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-rci-exit-"))
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


def summarize(trades: list[dict], label: str, *, exclude: set[str] | None = None) -> None:
    ex = exclude or set()
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in ex]
    wins = [t for t in closed if t["gain"] > 0]
    losses = [t for t in closed if t["gain"] < 0]
    pf = _calc_pf([{"gain": t["gain"]} for t in wins], [{"gain": t["gain"]} for t in losses])
    reasons: dict[str, dict] = defaultdict(lambda: {"n": 0, "pnl": 0})
    for t in closed:
        r = t.get("exit_reason") or "?"
        reasons[r]["n"] += 1
        reasons[r]["pnl"] += t["gain"]
    holds = [t["hold_days"] for t in closed]
    avg_hold = sum(holds) / len(holds) if holds else 0

    print(f"=== {label} ===")
    print(
        f"  {len(closed)}件  勝率{len(wins)/len(closed)*100:.1f}%  PF{pf}  "
        f"合計{sum(t['gain'] for t in closed):+,}円  平均保有{avg_hold:.1f}日"
    )
    for r, g in sorted(reasons.items(), key=lambda x: -x[1]["n"]):
        print(f"    {r}: {g['n']}件 {g['pnl']:+,}円")


def main() -> int:
    print("RCI下向き決済バックテスト（損切7%・RSI60・100日）")
    print("条件: RCIが反発(peak>=20)後、前日比5pt以上下落 → 決済")
    print()

    if not BASE.is_file():
        print(f"missing {BASE}")
        return 1

    rci_trades = run_backtest(rci_exit=True, cache=OUT)
    base_trades = json.loads(BASE.read_text(encoding="utf-8"))

    print("[10年全体]")
    summarize(base_trades, "現行（RCI決済OFF・損切7%）")
    summarize(rci_trades, "RCI下向き決済ON + 損切7%")
    b = sum(t["gain"] for t in base_trades if t.get("closed"))
    r = sum(t["gain"] for t in rci_trades if t.get("closed"))
    print(f"\n  差(RCI決済 - 現行): {r - b:+,}円")

    ex = {"2020"}
    print("\n[2020年除外]")
    summarize(base_trades, "現行", exclude=ex)
    summarize(rci_trades, "RCI決済ON", exclude=ex)
    b2 = sum(t["gain"] for t in base_trades if t.get("closed") and t["entry"][:4] not in ex)
    r2 = sum(t["gain"] for t in rci_trades if t.get("closed") and t["entry"][:4] not in ex)
    print(f"\n  差(RCI決済 - 現行): {r2 - b2:+,}円")
    print(f"\n保存: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
