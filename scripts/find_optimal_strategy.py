#!/usr/bin/env python3
"""決済条件 × 実運用ルール（50万・1-2銘柄）のグリッド探索."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from kaburadar3.analytics.backtest_deep import load_market_closes, market_return_at
from kaburadar3.analytics.backtest_report import _calc_pf, extract_trades_from_outdf, patch_config_past_period
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine
from kaburadar3.strategy.models import Judge, KabInf

from etf_exit_cache import build_etf_cache
from simulate_realistic_500k import (
    ETF_CODE,
    SimTrade,
    pick_stocks,
    scale_pnl,
    stock_batch_pnl,
)

CAPITAL = 500_000
PAST_DAYS = 3650


@dataclass
class ExitConfig:
    name: str
    stop_loss: bool
    stop_pct: float
    trades_path: Path | None = None


@dataclass
class OpRule:
    name: str
    etf_threshold: int = 8
    always_stock: bool = False
    skip: Callable[[int, float | None], bool] | None = None
    etf_when: Callable[[int, float | None], bool] | None = None


@dataclass
class Result:
    exit_name: str
    rule_name: str
    trades: int
    win_rate: float
    pf: float | None
    total_pnl: int
    pnl_2020: int
    pnl_2020_03: int
    max_loss: int
    score: float


def patch_config_full(
    text: str,
    *,
    past_period: int,
    stop_loss: bool,
    stop_pct: float,
) -> str:
    text = patch_config_past_period(text, past_period)
    val = 1 if stop_loss else 0
    text = re.sub(r"SCR_JDG_STOP_LOSS\s*=\s*\d+", f"SCR_JDG_STOP_LOSS = {val}", text)
    text = re.sub(r"SCR_STOP_LOSS_PCT\s*=\s*[\d.]+", f"SCR_STOP_LOSS_PCT = {stop_pct}", text)
    return text


def run_backtest(exit_cfg: ExitConfig, *, limit: int | None = None) -> list[dict]:
    if exit_cfg.trades_path and exit_cfg.trades_path.is_file():
        return json.loads(exit_cfg.trades_path.read_text(encoding="utf-8"))

    base = (ROOT / "config" / "config_lo.ini").read_text(encoding="utf-8")
    text = patch_config_full(
        base, past_period=PAST_DAYS, stop_loss=exit_cfg.stop_loss, stop_pct=exit_cfg.stop_pct
    )
    tmp = Path(tempfile.mkdtemp(prefix="kaburadar3-opt-"))
    cfg = tmp / "config_lo.ini"
    cfg.write_text(text, encoding="utf-8")
    os.environ["KABURADAR_CONFIG"] = str(cfg)

    conn, cursor = db.connect_db()
    trades: list[dict] = []
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set").set_index("code")
        enabled = [c for c in codes if str(c) in df_set.index and df_set.at[str(c), "Enable"] != 0]
        if limit:
            enabled = enabled[:limit]
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

    cache = ROOT / "output" / "optimize" / f"trades_{exit_cfg.name}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding="utf-8")
    exit_cfg.trades_path = cache
    return trades


def make_judge(exit_cfg: ExitConfig) -> Judge:
    jg = Judge(conf.CONF_SEC_SCR)
    jg.jdg_stop_loss = 1 if exit_cfg.stop_loss else 0
    jg.stop_loss_pct = exit_cfg.stop_pct
    return jg


def run_op_rule(
    by_day: dict[str, list[dict]],
    rule: OpRule,
    *,
    etf_cache: dict[str, dict],
    market: dict[date, float],
    capital: float = CAPITAL,
) -> list[SimTrade]:
    out: list[SimTrade] = []
    busy_until: date | None = None

    def mkt20(day_s: str) -> float | None:
        return market_return_at(market, date.fromisoformat(day_s))

    for day_s in sorted(by_day):
        day = date.fromisoformat(day_s)
        if busy_until and day <= busy_until:
            continue

        rows = [t for t in by_day[day_s] if t.get("closed")]
        if not rows:
            continue
        n = len(rows)
        m = mkt20(day_s)

        if rule.skip and rule.skip(n, m):
            continue

        use_etf = False
        if not rule.always_stock:
            if rule.etf_when:
                use_etf = rule.etf_when(n, m)
            else:
                use_etf = n >= rule.etf_threshold

        if use_etf:
            etf = etf_cache.get(day_s)
            if not etf:
                continue
            pnl = scale_pnl(float(etf["buy_price"]), float(etf["exit_price"]), capital)
            busy_until = date.fromisoformat(etf["exit"][:10])
            out.append(
                SimTrade(
                    entry=etf["entry"],
                    exit=etf["exit"],
                    kind="etf",
                    codes=[ETF_CODE],
                    buy_price=float(etf["buy_price"]),
                    exit_price=float(etf["exit_price"]),
                    pnl=pnl,
                    hold_days=int(etf["hold_days"]),
                    exit_reason=str(etf["exit_reason"]),
                    signal_count=n,
                )
            )
        else:
            picks = pick_stocks(rows)
            if not picks:
                continue
            pnl, avg_buy, avg_exit, hold, reason = stock_batch_pnl(picks, capital)
            busy_until = max(date.fromisoformat(t["exit"][:10]) for t in picks)
            out.append(
                SimTrade(
                    entry=day_s,
                    exit=busy_until.isoformat(),
                    kind="stock",
                    codes=[t["code"] for t in picks],
                    buy_price=avg_buy,
                    exit_price=avg_exit,
                    pnl=pnl,
                    hold_days=hold,
                    exit_reason=reason,
                    signal_count=n,
                )
            )
    return out


def compute_score(total: int, pnl_2020: int, max_loss: int, pf: float | None) -> float:
    """実運用向け: 10年利益 + 2020耐え + 最大損抑制."""
    s = float(total)
    # 2020が大赤字なら強いペナルティ
    if pnl_2020 < 0:
        s += pnl_2020 * 0.8
    if pnl_2020 < -150_000:
        s -= (abs(pnl_2020) - 150_000) * 1.5
    # 1回-10万超はリスクペナルティ
    if max_loss < -100_000:
        s += (max_loss + 100_000) * 2.0
    # PFボーナス（弱め）
    if pf:
        s += (pf - 1.0) * 50_000
    return round(s, 0)


def build_rules() -> list[OpRule]:
    return [
        OpRule("常に個別1-2", always_stock=True),
        OpRule("8+→ETF/未満→個別", etf_threshold=8),
        OpRule("6+→ETF", etf_threshold=6),
        OpRule("12+→ETF", etf_threshold=12),
        OpRule("8+→ETF/50+停止", etf_threshold=8, skip=lambda n, m: n >= 50),
        OpRule("8+→ETF/地合<-18%停止", etf_threshold=8, skip=lambda n, m: m is not None and m < -18),
        OpRule("常に個別/地合<-18%停止", always_stock=True, skip=lambda n, m: m is not None and m < -18),
        OpRule("8+→ETF/30+且地合<-10%停止", etf_threshold=8, skip=lambda n, m: n >= 30 and m is not None and m < -10),
        OpRule(
            "8+且地合>=-15%→ETF/他個別",
            etf_threshold=8,
            etf_when=lambda n, m: n >= 8 and (m is None or m >= -15),
        ),
        OpRule(
            "8+且地合>=-12%→ETF/他個別",
            etf_threshold=8,
            etf_when=lambda n, m: n >= 8 and (m is None or m >= -12),
        ),
        OpRule("8+→ETF/地合<-15%は停止", etf_threshold=8, skip=lambda n, m: m is not None and m < -15),
        OpRule("常に個別/50+停止", always_stock=True, skip=lambda n, m: n >= 50),
        OpRule("8+→ETF/80+停止", etf_threshold=8, skip=lambda n, m: n >= 80),
    ]


def build_exit_configs(*, run_missing: bool) -> list[ExitConfig]:
    configs = [
        ExitConfig("損切3%", True, 3.0, ROOT / "output" / "backtest_10y" / "trades.json"),
        ExitConfig("損切OFF", False, 3.0, ROOT / "output" / "backtest_no_stoploss" / "trades_no_stoploss.json"),
        ExitConfig("損切5%", True, 5.0, ROOT / "output" / "optimize" / "trades_損切5%.json"),
        ExitConfig("損切7%", True, 7.0, ROOT / "output" / "optimize" / "trades_損切7%.json"),
    ]
    if run_missing:
        for cfg in configs:
            if not cfg.trades_path or not cfg.trades_path.is_file():
                print(f"  バックテスト実行: {cfg.name} …")
                run_backtest(cfg)
    return configs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-missing-backtests", action="store_true", help="未生成の trades.json を実行")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "optimize" / "grid_results.json")
    args = parser.parse_args()

    print("=== 最適解探索（50万・1ポジション・1-2銘柄） ===\n")
    exit_configs = build_exit_configs(run_missing=args.run_missing_backtests)
    rules = build_rules()

    scr = conf.CONF_SEC_SCR
    prm = KabInf(
        sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
        srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
        srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
    )

    conn, cursor = db.connect_db()
    market = load_market_closes(cursor)
    results: list[Result] = []

    try:
        for ex in exit_configs:
            print(f"\n--- 決済: {ex.name} ---")
            if args.limit:
                trades = run_backtest(ex, limit=args.limit)
            elif ex.trades_path and ex.trades_path.is_file():
                trades = json.loads(ex.trades_path.read_text(encoding="utf-8"))
            else:
                trades = run_backtest(ex)

            by_day: dict[str, list[dict]] = defaultdict(list)
            for t in trades:
                if t.get("closed"):
                    by_day[t["entry"][:10]].append(t)

            jg = make_judge(ex)
            etf_days = [d for d, rows in by_day.items() if len(rows) >= 6]
            print(f"  ETFキャッシュ {len(etf_days)}日 …", flush=True)
            etf_cache = build_etf_cache(sorted(etf_days), jg=jg, prm=prm, conn=conn, cursor=cursor)
            for rule in rules:
                sim = run_op_rule(by_day, rule, etf_cache=etf_cache, market=market)
                if not sim:
                    continue
                wins = [t for t in sim if t.pnl > 0]
                losses = [t for t in sim if t.pnl < 0]
                total = sum(t.pnl for t in sim)
                pnl_2020 = sum(t.pnl for t in sim if t.entry.startswith("2020"))
                pnl_2020_03 = sum(t.pnl for t in sim if t.entry.startswith("2020-03"))
                max_loss = min(t.pnl for t in sim)
                pf = _calc_pf([{"gain": t.pnl} for t in wins], [{"gain": t.pnl} for t in losses])
                wr = len(wins) / len(sim) * 100
                sc = compute_score(total, pnl_2020, max_loss, pf)
                results.append(
                    Result(ex.name, rule.name, len(sim), round(wr, 1), pf, total, pnl_2020, pnl_2020_03, max_loss, sc)
                )
    finally:
        db.close_db(conn)

    results.sort(key=lambda r: -r.score)

    print("\n" + "=" * 100)
    print("TOP15（総合スコア = 10年利益 + 2020耐え + 最大損ペナルティ）")
    print("=" * 100)
    print(f"{'順':>3} {'決済':<10} {'運用ルール':<28} {'件':>4} {'勝率':>6} {'PF':>5} {'10年':>10} {'2020':>9} {'3月':>8} {'最大損':>8} {'Score':>8}")
    for i, r in enumerate(results[:15], 1):
        print(
            f"{i:3} {r.exit_name:<10} {r.rule_name:<28} {r.trades:4} {r.win_rate:5.1f}% "
            f"{r.pf or 0:5.2f} {r.total_pnl:+10,} {r.pnl_2020:+9,} {r.pnl_2020_03:+8,} {r.max_loss:+8,} {r.score:+8,.0f}"
        )

    # 2020重視ランキング
    results_2020 = sorted(results, key=lambda r: (-r.pnl_2020, -r.total_pnl))
    print("\n" + "=" * 100)
    print("2020年重視 TOP10")
    print("=" * 100)
    for i, r in enumerate(results_2020[:10], 1):
        print(
            f"{i:2} {r.exit_name:<10} {r.rule_name:<28} 2020{r.pnl_2020:+9,} 10年{r.total_pnl:+10,} PF{r.pf}"
        )

    # 10年純利益TOP
    results_pnl = sorted(results, key=lambda r: -r.total_pnl)
    print("\n" + "=" * 100)
    print("10年利益 TOP10")
    print("=" * 100)
    for i, r in enumerate(results_pnl[:10], 1):
        print(
            f"{i:2} {r.exit_name:<10} {r.rule_name:<28} {r.total_pnl:+10,} 2020{r.pnl_2020:+9,} max{r.max_loss:+8,}"
        )

    best = results[0]
    print("\n" + "=" * 100)
    print("【推奨】")
    print(f"  決済: {best.exit_name}")
    print(f"  運用: {best.rule_name}")
    print(f"  10年 +{best.total_pnl:,}円 / 2020 {best.pnl_2020:+,}円 / 最大1回 {best.max_loss:+,}円 / PF {best.pf}")
    print("=" * 100)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n全結果: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
