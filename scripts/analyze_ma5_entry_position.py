#!/usr/bin/env python3
"""エントリー時のMA5位置と、MA5スキップ（含み損）の関係を分析."""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.backtest_report import patch_config_past_period
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.ma5 import high_reached_ma5_offset
from kaburadar3.strategy.models import KabInf

PAST_DAYS = 3650


def run_collect() -> list[dict]:
    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch_config_past_period(base, PAST_DAYS)
    text = re.sub(r"SCR_MA5_OFFSET_PCT\s*=\s*[\d.-]+", "SCR_MA5_OFFSET_PCT = -2.0", text)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-ma5-pos-"))
    cfg = tmp / "config_lo.ini"
    cfg.write_text(text, encoding="utf-8")
    os.environ["KABURADAR_CONFIG"] = str(cfg)
    offset = float(conf.get_config(conf.CONF_SEC_SCR, conf.CONF_KEY_SCR_MA5_OFFSET_PCT, default="-2"))
    rows: list[dict] = []
    conn, cursor = db.connect_db()
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
            for code in enabled[:80]:  # サンプル80銘柄
                if engine.backtst_proc(code, None, prm, conn=conn, cursor=cursor) == -1:
                    continue
                out = prm.outdf
                if out is None or out.empty:
                    continue
                buy_price = 0.0
                entry_sma5 = 0.0
                for _, row in out.iterrows():
                    mark = str(row.get("mark", ""))
                    if mark == "新買":
                        buy_price = float(row["close"])
                        entry_sma5 = float(row.get("SMA5_PREV", row.get("SMA5", 0)) or 0)
                        continue
                    if buy_price <= 0:
                        continue
                    sma5p = float(row.get("SMA5_PREV", 0) or 0)
                    high = float(row["high"])
                    close = float(row["close"])
                    if sma5p <= 0:
                        continue
                    if not high_reached_ma5_offset(high, sma5p, offset):
                        continue
                    entry_above = buy_price > entry_sma5 * 1.005 if entry_sma5 > 0 else False
                    entry_below = buy_price < entry_sma5 * 0.995 if entry_sma5 > 0 else False
                    in_profit = close > buy_price
                    rows.append(
                        {
                            "entry_above_ma5": entry_above,
                            "entry_below_ma5": entry_below,
                            "in_profit": in_profit,
                            "skipped": not in_profit,  # profit_only=1
                        }
                    )
                    if mark == "返売":
                        buy_price = 0.0
    finally:
        db.close_db(conn)
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def main() -> int:
    print("analyzing (80 codes sample)...", flush=True)
    rows = run_collect()
    if not rows:
        print("no data")
        return 1
    skip = [r for r in rows if r["skipped"]]
    take = [r for r in rows if not r["skipped"]]
    print(f"\n=== MA5シグナル日（高値が5日線付近） {len(rows)}件 ===")
    print(f"  profit_only=1で決済: {len(take)}件")
    print(f"  含み損でスキップ:     {len(skip)}件")

    def pct(sub: list[dict], key: str) -> float:
        return round(sum(1 for r in sub if r[key]) / len(sub) * 100, 1) if sub else 0

    print("\n【エントリー時 vs 前日MA5】")
    print(f"{'':20} {'決済(含み益)':>12} {'スキップ(含み損)':>16}")
    print(f"{'エントリーがMA5より上':>20} {pct(take,'entry_above_ma5'):>11}% {pct(skip,'entry_above_ma5'):>15}%")
    print(f"{'エントリーがMA5より下':>20} {pct(take,'entry_below_ma5'):>11}% {pct(skip,'entry_below_ma5'):>15}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
