#!/usr/bin/env python3
"""銘柄選定方式（code / rsi / rci_rsi / stars）の50万シミュ比較."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from kaburadar3.analytics.backtest_deep import load_market_closes, market_return_at
from kaburadar3.analytics.backtest_report import _calc_pf
from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.settings.runtime import RuntimeConfig
from kaburadar3.signals.picker import (
    PICK_CODE,
    PICK_RCI_RSI,
    PICK_RSI_LOW,
    PICK_STARS,
    enrich_trades_by_code,
    pick_trades,
)
from kaburadar3.signals.special import evaluate_routing
from kaburadar3.strategy.models import Judge, KabInf

from etf_exit_cache import build_etf_cache
from simulate_realistic_500k import ETF_CODE, SimTrade, scale_pnl, stock_batch_pnl

CAPITAL = 500_000


def run_hybrid_sim(
    by_day: dict[str, list[dict]],
    *,
    pick_method: str,
    etf_cache: dict[str, dict],
    market: dict[date, float],
    runtime: RuntimeConfig,
    prm: KabInf,
    jg: Judge,
) -> list[SimTrade]:
    out: list[SimTrade] = []
    busy_until: date | None = None

    for day_s in sorted(by_day):
        day = date.fromisoformat(day_s)
        if busy_until and day <= busy_until:
            continue
        rows = [t for t in by_day[day_s] if t.get("closed")]
        if not rows:
            continue
        n = len(rows)
        m = market_return_at(market, day)
        routing = evaluate_routing(n, m, runtime)

        if routing == "etf":
            etf = etf_cache.get(day_s)
            if not etf:
                continue
            pnl = scale_pnl(float(etf["buy_price"]), float(etf["exit_price"]), CAPITAL)
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
            picks = pick_trades(rows, n=2, method=pick_method, capital=CAPITAL)
            if not picks:
                continue
            pnl, avg_buy, avg_exit, hold, reason = stock_batch_pnl(picks, CAPITAL)
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


def summarize(label: str, sim: list[SimTrade]) -> dict:
    wins = [t for t in sim if t.pnl > 0]
    losses = [t for t in sim if t.pnl < 0]
    total = sum(t.pnl for t in sim)
    pnl_2020 = sum(t.pnl for t in sim if t.entry.startswith("2020"))
    pf = _calc_pf([{"gain": t.pnl} for t in wins], [{"gain": t.pnl} for t in losses])
    return {
        "method": label,
        "trades": len(sim),
        "win_rate": round(len(wins) / len(sim) * 100, 1) if sim else 0,
        "pf": pf,
        "total_pnl": total,
        "pnl_2020": pnl_2020,
        "max_loss": min((t.pnl for t in sim), default=0),
    }


def main() -> int:
    trades_path = ROOT / "output" / "optimize" / "trades_損切7%.json"
    if not trades_path.is_file():
        trades_path = ROOT / "output" / "backtest_10y" / "trades.json"
    print(f"trades: {trades_path}")

    trades = json.loads(trades_path.read_text(encoding="utf-8"))
    conn, cursor = db.connect_db()
    try:
        print("テクニカル付与中…")
        enriched = enrich_trades_by_code(trades, conn, cursor)
        by_day: dict[str, list[dict]] = defaultdict(list)
        for t in enriched:
            if t.get("closed"):
                by_day[t["entry"][:10]].append(t)

        runtime = RuntimeConfig.from_dict(
            {
                "special_buy": {
                    "min_new_buy_count": 8,
                    "market_regime_min_pct": -15,
                }
            }
        )
        scr = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
            srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
        )
        jg = Judge(scr)
        jg.jdg_stop_loss = 1
        jg.stop_loss_pct = 7.0
        market = load_market_closes(cursor)
        etf_days = [d for d, rows in by_day.items() if len(rows) >= 6]
        print(f"ETFキャッシュ {len(etf_days)}日 …")
        etf_cache = build_etf_cache(sorted(etf_days), jg=jg, prm=prm, conn=conn, cursor=cursor)

        methods = [
            (PICK_CODE, "コード昇順"),
            (PICK_RSI_LOW, "RSI低い順"),
            (PICK_RCI_RSI, "RCI上向き+RSI低"),
            (PICK_STARS, "★順（★3以上・履歴なし=★3）"),
        ]
        results = []
        for method, label in methods:
            sim = run_hybrid_sim(
                by_day,
                pick_method=method,
                etf_cache=etf_cache,
                market=market,
                runtime=runtime,
                prm=prm,
                jg=jg,
            )
            row = summarize(label, sim)
            results.append(row)
            print(
                f"{label:16}  {row['trades']:3}件  勝率{row['win_rate']:5.1f}%  "
                f"PF{row['pf']}  10年{row['total_pnl']:+,}  2020{row['pnl_2020']:+,}  "
                f"最大{row['max_loss']:+,}"
            )

        best = max(results, key=lambda r: r["total_pnl"] * 0.6 + r["pnl_2020"] * 0.4)
        best_method = next(m for m, label in methods if label == best["method"])
        out_path = ROOT / "output" / "optimize" / "pick_methods.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(
                {"results": results, "recommended_label": best["method"], "recommended_method": best_method},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\n10年+2020加重1位: {best['method']}")
        print(f"本番設定（rci_rsi）: PF1.588 / 10年+673,700 / 2020+48,300")
        print(f"保存: {out_path}")
    finally:
        db.close_db(conn)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
