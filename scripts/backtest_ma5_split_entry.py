#!/usr/bin/env python3
"""MA5上/下エントリーで決済ルールを分けたバックテスト."""

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
CACHE = ROOT / "output" / "optimize" / "trades_ma5_split_entry.json"
CACHE_HONEST = ROOT / "output" / "optimize" / "trades_ma5_split_profit0.json"


def patch(text: str, *, split: int, profit_only: int) -> str:
    text = patch_config_past_period(text, PAST_DAYS)
    text = re.sub(r"SCR_MA5_SPLIT_BY_ENTRY\s*=\s*\d+", f"SCR_MA5_SPLIT_BY_ENTRY = {split}", text)
    if "SCR_MA5_SPLIT_BY_ENTRY" not in text:
        text = text.replace("SCR_MA5_PROFIT_ONLY = 1", "SCR_MA5_PROFIT_ONLY = 1\nSCR_MA5_SPLIT_BY_ENTRY = 1")
    text = re.sub(r"SCR_MA5_PROFIT_ONLY\s*=\s*\d+", f"SCR_MA5_PROFIT_ONLY = {profit_only}", text)
    text = re.sub(r"SCR_MA5_OFFSET_PCT\s*=\s*[\d.-]+", "SCR_MA5_OFFSET_PCT = -2.0", text)
    text = re.sub(r"SCR_RSI60_HOLD_RCI_UP\s*=\s*\d+", "SCR_RSI60_HOLD_RCI_UP = 1", text)
    return text


def stats(trades: list[dict], *, above_only: bool | None = None) -> dict:
    closed = [t for t in trades if t.get("closed") and t["entry"][:4] not in EXCLUDE]
    if above_only is True:
        closed = [t for t in closed if t.get("entry_above_ma5")]
    elif above_only is False:
        closed = [t for t in closed if not t.get("entry_above_ma5")]
    wins = [t for t in closed if t["gain"] > 0]
    losses = [t for t in closed if t["gain"] < 0]
    wg = sorted(t["gain"] for t in wins)
    lg = sorted(t["gain"] for t in losses)
    pf = _calc_pf([{"gain": t["gain"] for t in wins}], [{"gain": t["gain"] for t in losses}])
    reasons = {}
    for t in closed:
        r = t.get("exit_reason") or "その他"
        reasons[r] = reasons.get(r, 0) + 1
    return {
        "n": len(closed),
        "win": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total": sum(t["gain"] for t in closed),
        "pf": pf,
        "med_w": wg[len(wg) // 2] if wg else 0,
        "med_l": lg[len(lg) // 2] if lg else 0,
        "reasons": reasons,
    }


def run_backtest(*, split: int, profit_only: int = 1) -> list[dict]:
    cache = CACHE_HONEST if profit_only == 0 else CACHE if split else ROOT / "output" / "optimize" / "trades_ma5_split_off.json"
    if split and cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch(base, split=split, profit_only=profit_only)
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-split-"))
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
    if split:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    return trades


def _print_block(trades: list[dict], *, title: str) -> None:
    a = stats(trades, above_only=True)
    b = stats(trades, above_only=False)
    c = stats(trades)
    print(f"\n=== {title}（2020除） ===")
    print("【MA5上】MA5割れ撤退 + RSI60利確")
    print(f"  取引{a['n']}  勝率{a['win']}%  損益{a['total']:+,}  PF{a['pf']}")
    print(f"  決済内訳: {a['reasons']}")
    print(f"  勝中央{a['med_w']:+,}  負中央{a['med_l']:+,}")
    print("【MA5下】MA5接近利確 + RSI60/RCI")
    print(f"  取引{b['n']}  勝率{b['win']}%  損益{b['total']:+,}  PF{b['pf']}")
    print(f"  決済内訳: {b['reasons']}")
    print(f"  勝中央{b['med_w']:+,}  負中央{b['med_l']:+,}")
    print("【合算】")
    print(f"  取引{c['n']}  勝率{c['win']}%  損益{c['total']:+,}  PF{c['pf']}")


def main() -> int:
    print("running 正直版 profit_only=0 ...", flush=True)
    honest = run_backtest(split=1, profit_only=0)
    _print_block(honest, title="分割ルール・正直版（profit_only=0）")
    print(
        "\n※ profit_only=1 の88%台勝率は「引けプラスの日だけMA5決済」"
        "のフィルタで水増し。比較・採用判断には使わない。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
