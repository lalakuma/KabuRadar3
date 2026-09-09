#!/usr/bin/env python3
"""5日線オフセット・モードのグリッド（勝率最大化探索）."""

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
CACHE_DIR = ROOT / "output" / "optimize" / "ma5_grid"

OFFSETS_FINE = [round(x * 0.25, 2) for x in range(-12, 9)]  # -3.0 .. +2.0
OFFSETS_QUICK = [round(x * 0.5, 1) for x in range(-6, 5)]  # -3.0 .. +2.0 step 0.5
BAND_WIDTHS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
PULLBACK_WIDTHS = [1.0, 1.5, 2.0, 2.5]


def patch(
    text: str,
    *,
    mode: str,
    offset: float | None = None,
    proximity: float | None = None,
) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_JDG_MA5_EXIT\s*=\s*\d+", "SCR_JDG_MA5_EXIT = 1", text)
    text = re.sub(r"SCR_MA5_EXIT_MODE\s*=\s*\w+", f"SCR_MA5_EXIT_MODE = {mode}", text)
    if "SCR_MA5_EXIT_MODE" not in text:
        text = text.replace("SCR_JDG_MA5_EXIT = 1", f"SCR_JDG_MA5_EXIT = 1\nSCR_MA5_EXIT_MODE = {mode}")
    if offset is not None:
        text = re.sub(r"SCR_MA5_OFFSET_PCT\s*=\s*[\d.-]+", f"SCR_MA5_OFFSET_PCT = {offset}", text)
        if "SCR_MA5_OFFSET_PCT" not in text:
            text += f"\nSCR_MA5_OFFSET_PCT = {offset}\n"
    if proximity is not None:
        text = re.sub(r"SCR_MA5_PROXIMITY_PCT\s*=\s*[\d.]+", f"SCR_MA5_PROXIMITY_PCT = {proximity}", text)
    text = re.sub(r"SCR_RSI60_HOLD_RCI_UP\s*=\s*\d+", "SCR_RSI60_HOLD_RCI_UP = 1", text)
    text = re.sub(r"SCR_JDG_RCI_EXIT\s*=\s*\d+", "SCR_JDG_RCI_EXIT = 0", text)
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", "SCR_JDG_STOP_LOSS = 1", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", "SCR_STOP_LOSS_PCT = 7.0", text)
    text = re.sub(r"SCR_MA5_PROFIT_ONLY\s*=\s*\d+", "SCR_MA5_PROFIT_ONLY = 1", text)
    return text


def cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def run_backtest(name: str, text: str) -> list[dict]:
    path = cache_path(name)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))

    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-ma5-grid-"))
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    return trades


def stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in EXCLUDE]
    wins = [t for t in closed if t["gain"] > 0]
    losses = [t for t in closed if t["gain"] < 0]
    wg = sorted(t["gain"] for t in wins)
    lg = sorted(t["gain"] for t in losses)
    pf = _calc_pf([{"gain": t["gain"] for t in wins}], [{"gain": t["gain"] for t in losses}])
    return {
        "total": sum(t["gain"] for t in closed),
        "win": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "pf": pf,
        "ma5": sum(1 for t in closed if t.get("exit_reason") == "MA5"),
        "rsi60": sum(1 for t in closed if t.get("exit_reason") == "RSI60"),
        "stops": sum(1 for t in closed if t.get("exit_reason") == "損切り"),
        "med_w": wg[len(wg) // 2] if wg else 0,
        "trades": len(closed),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="全組み合わせ（0.25刻み・時間かかる）")
    parser.add_argument("--offset-only", action="store_true", help="offsetモードのみ")
    args = parser.parse_args()

    offsets = OFFSETS_FINE if args.full else OFFSETS_QUICK
    band_widths = BAND_WIDTHS if args.full else [1.5]
    pullback_widths = PULLBACK_WIDTHS if args.full else [1.5]

    base_ini = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    rows: list[dict] = []

    hold_cache = ROOT / "output" / "optimize" / "trades_RSI60_hold_RCI.json"
    if hold_cache.is_file():
        rows.append({"label": "現行(MA5なし)", **stats(json.loads(hold_cache.read_text(encoding="utf-8")))})

    for off in offsets:
        label = f"offset {off:+.2f}%"
        name = f"offset_{off:+.2f}".replace("+", "p").replace("-", "m").replace(".", "d")
        print(f"running {label}...", flush=True)
        text = patch(base_ini, mode="offset", offset=off)
        trades = run_backtest(name, text)
        rows.append({"label": label, "mode": "offset", "param": off, **stats(trades)})

    if args.offset_only:
        band_widths = []
        pullback_widths = []

    for prox in band_widths:
        label = f"band ±{prox}%"
        name = f"band_{prox}".replace(".", "d")
        print(f"running {label}...", flush=True)
        text = patch(base_ini, mode="band", proximity=prox)
        trades = run_backtest(name, text)
        rows.append({"label": label, "mode": "band", "param": prox, **stats(trades)})

    for prox in pullback_widths:
        label = f"pullback ±{prox}%"
        name = f"pullback_{prox}".replace(".", "d")
        print(f"running {label}...", flush=True)
        text = patch(base_ini, mode="pullback", proximity=prox)
        trades = run_backtest(name, text)
        rows.append({"label": label, "mode": "pullback", "param": prox, **stats(trades)})

    by_win = sorted(rows, key=lambda r: (-r["win"], -r["total"]))
    by_pnl = sorted(rows, key=lambda r: -r["total"])

    print("\n=== MA5グリッド 勝率TOP10（2020除） ===")
    print(f"{'設定':<18} {'勝率':>6} {'損益':>10} {'PF':>6} {'MA5':>5} {'RSI60':>6} {'損切':>5} {'勝中央':>7}")
    for r in by_win[:10]:
        print(
            f"{r['label']:<18} {r['win']:>5.1f}% {r['total']:>+10,} {r['pf']:>6} "
            f"{r['ma5']:>5} {r['rsi60']:>6} {r['stops']:>5} {r['med_w']:>+7,}"
        )

    print("\n=== 損益TOP5 ===")
    for r in by_pnl[:5]:
        print(f"{r['label']:<18} {r['total']:>+10,}  勝率{r['win']:.1f}%")

    best = by_win[0]
    print(f"\n最高勝率: {best['label']} → {best['win']}%  損益{best['total']:+,}  PF{best['pf']}")

    out = CACHE_DIR / "grid_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"by_win": by_win, "by_pnl": by_pnl}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
