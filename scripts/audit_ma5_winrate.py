#!/usr/bin/env python3
"""MA5高勝率の要因監査（profit_only / 高値vs終値）."""

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

from kaburadar3.analytics.backtest_report import extract_trades_from_outdf, patch_config_past_period
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import KabInf

PAST_DAYS = 3650
EXCLUDE = {"2020"}
CACHE = ROOT / "output" / "optimize" / "ma5_grid_prev" / "offset_m2d00.json"


def stats(trades: list[dict]) -> dict:
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in EXCLUDE]
    wins = [t for t in closed if t["gain"] > 0]
    losses = [t for t in closed if t["gain"] < 0]
    ma5 = [t for t in closed if t.get("exit_reason") == "MA5"]
    ma5_w = [t for t in ma5 if t["gain"] > 0]
    ma5_l = [t for t in ma5 if t["gain"] < 0]
    return {
        "trades": len(closed),
        "win_pct": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total": sum(t["gain"] for t in closed),
        "ma5_n": len(ma5),
        "ma5_win_pct": round(len(ma5_w) / len(ma5) * 100, 1) if ma5 else 0,
        "ma5_losses": len(ma5_l),
        "med_w": sorted(t["gain"] for t in wins)[len(wins) // 2] if wins else 0,
        "med_l": sorted(t["gain"] for t in losses)[len(losses) // 2] if losses else 0,
    }


def run_backtest(*, profit_only: int) -> list[dict]:
    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch_config_past_period(base, PAST_DAYS)
    text = re.sub(r"SCR_MA5_OFFSET_PCT\s*=\s*[\d.-]+", "SCR_MA5_OFFSET_PCT = -2.0", text)
    text = re.sub(r"SCR_MA5_PROFIT_ONLY\s*=\s*\d+", f"SCR_MA5_PROFIT_ONLY = {profit_only}", text)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-audit-"))
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
    return trades


def main() -> int:
    print("=== MA5高勝率 監査（offset -2.0%, 2020除） ===\n")

    if CACHE.is_file():
        s1 = stats(json.loads(CACHE.read_text(encoding="utf-8")))
        print("【現設定】profit_only=1（高値でシグナル、終値が含み益のときだけ決済）")
        print(f"  全体勝率: {s1['win_pct']}%  損益: {s1['total']:+,}")
        print(f"  MA5決済: {s1['ma5_n']}件  MA5勝率: {s1['ma5_win_pct']}%  MA5負け: {s1['ma5_losses']}件")
        print(f"  勝中央: {s1['med_w']:+,}  負中央: {s1['med_l']:+,}")

    print("\nrunning profit_only=0 ...", flush=True)
    s0 = stats(run_backtest(profit_only=0))
    print("\n【比較】profit_only=0（高値到達なら終値で決済、含み損でも可）")
    print(f"  全体勝率: {s0['win_pct']}%  損益: {s0['total']:+,}")
    print(f"  MA5決済: {s0['ma5_n']}件  MA5勝率: {s0['ma5_win_pct']}%  MA5負け: {s0['ma5_losses']}件")
    print(f"  勝中央: {s0['med_w']:+,}  負中央: {s0['med_l']:+,}")

    if CACHE.is_file():
        print(f"\n勝率差(profit_only効果): {s1['win_pct'] - s0['win_pct']:+.1f}pt")
    print(
        "\n【結論の目安】"
        "\n  profit_only=1 は「5日線付近まで上がったが終値は含み損」の取引を"
        "\n  MA5決済から除外し、損切/RSI60等に回す → 勝率を人工的に押し上げる。"
        "\n  高値トリガー+終値決済の組み合わせ自体も、場中の利確とは異なる。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
