#!/usr/bin/env python3
"""実運用想定: 50万・1〜2銘柄 vs 8件以上はETF(1306).

10年バックテスト trades.json を再利用し、
- 8件以上の日: ETF 50万
- それ以外: 通知上位1〜2銘柄（コード昇順）に50万
をポートフォリオ制約（同時1ポジション）で比較する。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from kaburadar3.analytics.backtest_report import _calc_pf, infer_exit_reason
from kaburadar3.data import repository as db
from kaburadar3.domain import constants as DEF
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine, rci as tc_rci, rsi as tc_rsi
from kaburadar3.strategy.models import CodePrice, Judge, KabInf, TradeInfo

ETF_CODE = "1306"
CAPITAL = 500_000
SIGNAL_THRESHOLD = 8
MAX_STOCKS = 2


@dataclass
class SimTrade:
    entry: str
    exit: str
    kind: str  # "etf" | "stock"
    codes: list[str]
    buy_price: float
    exit_price: float
    pnl: int
    hold_days: int
    exit_reason: str
    signal_count: int


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(str(value)[:10]).date()


def scale_pnl(buy_price: float, exit_price: float, capital: float) -> int:
    if buy_price <= 0 or exit_price <= 0:
        return 0
    lots = int(capital // (buy_price * 100))
    if lots <= 0:
        return 0
    return int(lots * 100 * (exit_price - buy_price))


def split_capital(n_positions: int, total: float) -> list[float]:
    n = max(1, min(n_positions, MAX_STOCKS))
    base = int(total // n)
    rem = int(total - base * n)
    parts = [base] * n
    if rem and parts:
        parts[0] += rem
    return parts


from kaburadar3.signals.picker import PICK_RCI_RSI, pick_trades


def pick_stocks(day_trades: list[dict], *, exclude_etf: bool = True) -> list[dict]:
    _ = exclude_etf
    return pick_trades(day_trades, n=MAX_STOCKS, method=PICK_RCI_RSI)


def _build_price_frame(conn, cursor, code: str, start: date, end: date) -> pd.DataFrame:
    df = db.read_rec_period(conn, cursor, str(code), start.isoformat(), end.isoformat())
    if df is None or df.empty:
        return pd.DataFrame()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
    df["SMA5"] = df["close"].rolling(window=5).mean()
    df["SMA25"] = df["close"].rolling(window=25).mean()
    out = df.set_index("datetime").loc[:, ["open", "high", "low", "close", "volume", "SMA5", "SMA25"]]
    out = tc_rsi.rsi_tradingview(out, 4)
    jg = Judge(conf.CONF_SEC_SCR)
    out = tc_rci.attach_rci(out, period=jg.rci_period)
    return out


def simulate_forced_etf_exit(
    conn,
    cursor,
    entry_day: date,
    *,
    prm: KabInf,
    jg: Judge,
) -> dict | None:
    """8件以上の日に1306を終値で買い、エンジンと同じ決済ルールで返す."""
    start = entry_day - timedelta(days=120)
    end = entry_day + timedelta(days=prm.sell_period + 30)
    df = _build_price_frame(conn, cursor, ETF_CODE, start, end)
    if df.empty:
        return None

    dates = [d.date() if hasattr(d, "date") else d for d in df.index]
    if entry_day not in dates:
        later = [d for d in dates if d >= entry_day]
        if not later:
            return None
        entry_day = later[0]

    entry_idx = dates.index(entry_day)
    if df.iloc[entry_idx]["SMA25"] != df.iloc[entry_idx]["SMA25"]:  # NaN
        return None

    cp = CodePrice()
    cp.code = ETF_CODE
    ti = TradeInfo()
    ti.sb_mode = DEF.MODE_BUY
    row0 = df.iloc[entry_idx]
    ti.buy_pos = 1
    ti.buy_price = float(row0["close"])
    buy_price = ti.buy_price

    bkdf = pd.DataFrame()
    cnt_buyholddays = 0
    for i in range(entry_idx, len(df)):
        row = df.iloc[i]
        wkdf = pd.DataFrame([row])
        bkdf = pd.concat([bkdf, wkdf], ignore_index=True)
        lastidx = len(bkdf) - 1

        cp.i_open = float(row["open"])
        cp.i_close = float(row["close"])
        cp.i_low = float(row["low"])
        cp.i_high = float(row["high"])
        cp.i_sma5 = float(row["SMA5"])
        cp.i_sma25 = float(row["SMA25"])

        if i == entry_idx:
            continue

        cnt_buyholddays += 1
        exit_now, exit_price = engine._buy_exit_signal(cp, ti, jg, bkdf, prm, cnt_buyholddays)
        if not exit_now:
            continue

        exit_day = dates[i]
        hold_days = cnt_buyholddays
        exit_row = row.copy()
        exit_row["close"] = exit_price
        reason = infer_exit_reason(
            buy_price,
            exit_row,
            hold_days,
            stop_pct=jg.stop_loss_pct,
            sell_period=prm.sell_period,
            rsi_hi=float(prm.srsi_hi),
        )
        return {
            "code": ETF_CODE,
            "entry": entry_day.isoformat(),
            "exit": exit_day.isoformat(),
            "buy_price": int(buy_price),
            "exit_price": int(exit_price),
            "hold_days": hold_days,
            "exit_reason": reason,
        }

    return None


def stock_batch_pnl(picks: list[dict], capital: float) -> tuple[int, float, float, int, str]:
    caps = split_capital(len(picks), capital)
    total = 0
    hold = 0
    reasons: list[str] = []
    buy_prices: list[float] = []
    exit_prices: list[float] = []
    for trade, cap in zip(picks, caps):
        total += scale_pnl(float(trade["buy_price"]), float(trade["exit_price"]), cap)
        hold = max(hold, int(trade["hold_days"]))
        reasons.append(str(trade.get("exit_reason") or ""))
        buy_prices.append(float(trade["buy_price"]))
        exit_prices.append(float(trade["exit_price"]))
    avg_buy = sum(buy_prices) / len(buy_prices) if buy_prices else 0.0
    avg_exit = sum(exit_prices) / len(exit_prices) if exit_prices else 0.0
    reason = reasons[0] if len(set(reasons)) == 1 else "混在"
    return total, avg_buy, avg_exit, hold, reason


def summarize(trades: list[SimTrade], label: str) -> None:
    if not trades:
        print(f"\n[{label}] 取引なし")
        return
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl < 0]
    total = sum(t.pnl for t in trades)
    pf = _calc_pf([{"gain": t.pnl} for t in wins], [{"gain": t.pnl} for t in losses])
    print(f"\n[{label}]")
    print(f"  取引 {len(trades)}  勝率 {len(wins)/len(trades)*100:.1f}%  PF {pf}  合計 {total:+,}円")
    print(f"  平均 {total/len(trades):+,.0f}円/件  中央値 {median(t.pnl for t in trades):+,.0f}円")
    print(f"  平均保有 {sum(t.hold_days for t in trades)/len(trades):.1f}日")
    etf = [t for t in trades if t.kind == "etf"]
    stk = [t for t in trades if t.kind == "stock"]
    if etf:
        print(f"  うちETF {len(etf)}件  合計 {sum(t.pnl for t in etf):+,}円")
    if stk:
        print(f"  うち個別 {len(stk)}件  合計 {sum(t.pnl for t in stk):+,}円")


def run_portfolio(
    by_day: dict[str, list[dict]],
    *,
    mode: str,
    conn,
    cursor,
    prm: KabInf,
    jg: Judge,
    threshold: int = SIGNAL_THRESHOLD,
    capital: float = CAPITAL,
) -> list[SimTrade]:
    """mode: hybrid | always_stock | always_etf_on8 (8+のみETF、それ以外スキップ)."""
    days = sorted(by_day)
    out: list[SimTrade] = []
    busy_until: date | None = None

    for day_s in days:
        day = _parse_date(day_s)
        if busy_until and day <= busy_until:
            continue

        rows = [t for t in by_day[day_s] if t.get("closed")]
        if not rows:
            continue
        n_signal = len(rows)
        use_etf = n_signal >= threshold

        if mode == "always_stock":
            use_etf = False
        elif mode == "always_etf_on8":
            if not use_etf:
                continue
        elif mode != "hybrid":
            raise ValueError(mode)

        if use_etf:
            etf = simulate_forced_etf_exit(conn, cursor, day, prm=prm, jg=jg)
            if not etf:
                continue
            pnl = scale_pnl(float(etf["buy_price"]), float(etf["exit_price"]), capital)
            busy_until = _parse_date(etf["exit"])
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
                    signal_count=n_signal,
                )
            )
        else:
            picks = pick_stocks(rows)
            if not picks:
                continue
            pnl, avg_buy, avg_exit, hold, reason = stock_batch_pnl(picks, capital)
            busy_until = max(_parse_date(t["exit"]) for t in picks)
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
                    signal_count=n_signal,
                )
            )
    return out


def run_independent_8plus(
    by_day: dict[str, list[dict]],
    *,
    conn,
    cursor,
    prm: KabInf,
    jg: Judge,
    threshold: int = SIGNAL_THRESHOLD,
    capital: float = CAPITAL,
) -> tuple[list[SimTrade], list[SimTrade]]:
    """8件以上の日だけ、ポジション重複無視で ETF vs 個別1-2 を比較."""
    etf_trades: list[SimTrade] = []
    stock_trades: list[SimTrade] = []

    for day_s in sorted(by_day):
        rows = [t for t in by_day[day_s] if t.get("closed")]
        if len(rows) < threshold:
            continue
        n_signal = len(rows)

        etf = simulate_forced_etf_exit(conn, cursor, _parse_date(day_s), prm=prm, jg=jg)
        if etf:
            etf_trades.append(
                SimTrade(
                    entry=etf["entry"],
                    exit=etf["exit"],
                    kind="etf",
                    codes=[ETF_CODE],
                    buy_price=float(etf["buy_price"]),
                    exit_price=float(etf["exit_price"]),
                    pnl=scale_pnl(float(etf["buy_price"]), float(etf["exit_price"]), capital),
                    hold_days=int(etf["hold_days"]),
                    exit_reason=str(etf["exit_reason"]),
                    signal_count=n_signal,
                )
            )

        picks = pick_stocks(rows)
        if picks:
            pnl, avg_buy, avg_exit, hold, reason = stock_batch_pnl(picks, capital)
            stock_trades.append(
                SimTrade(
                    entry=day_s,
                    exit=max(t["exit"] for t in picks),
                    kind="stock",
                    codes=[t["code"] for t in picks],
                    buy_price=avg_buy,
                    exit_price=avg_exit,
                    pnl=pnl,
                    hold_days=hold,
                    exit_reason=reason,
                    signal_count=n_signal,
                )
            )
    return etf_trades, stock_trades


def print_worst_best(trades: list[SimTrade], label: str, n: int = 5) -> None:
    print(f"\n--- {label} ワースト{n} ---")
    for t in sorted(trades, key=lambda x: x.pnl)[:n]:
        print(
            f"  {t.entry}  通知{t.signal_count:3}  {t.kind} {','.join(t.codes)}  "
            f"{t.pnl:+,}円  {t.hold_days}日  {t.exit_reason}"
        )
    print(f"--- {label} ベスト{n} ---")
    for t in sorted(trades, key=lambda x: -x.pnl)[:n]:
        print(
            f"  {t.entry}  通知{t.signal_count:3}  {t.kind} {','.join(t.codes)}  "
            f"{t.pnl:+,}円  {t.hold_days}日  {t.exit_reason}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="50万実運用シミュレーション")
    parser.add_argument(
        "--trades",
        default=str(ROOT / "output" / "backtest_10y" / "trades.json"),
        help="バックテスト trades.json",
    )
    parser.add_argument("--capital", type=int, default=CAPITAL)
    parser.add_argument("--threshold", type=int, default=SIGNAL_THRESHOLD)
    parser.add_argument("--output", default="", help="JSON出力先（任意）")
    args = parser.parse_args()
    capital = float(args.capital)

    trades_raw = json.loads(Path(args.trades).read_text(encoding="utf-8"))
    by_day: dict[str, list[dict]] = defaultdict(list)
    for t in trades_raw:
        if t.get("closed"):
            by_day[t["entry"][:10]].append(t)

    scr = conf.CONF_SEC_SCR
    prm = KabInf(
        sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
        srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
        srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
    )
    jg = Judge(scr)

    conn, cursor = db.connect_db()
    try:
        days8 = sum(1 for d, rows in by_day.items() if len(rows) >= args.threshold)
        print("=" * 60)
        print(f"実運用シミュレーション（資金 {int(capital):,}円・{args.threshold}件以上でETF）")
        print(f"対象: {args.trades}")
        print(f"シグナル日 {len(by_day)} / {args.threshold}件以上 {days8}日")
        print("個別株: コード昇順で最大2銘柄・均等配分")
        print("ETF: 1306を当日終値で強制エントリー、同一決済ルール")
        print("=" * 60)

        etf8, stk8 = run_independent_8plus(
            by_day, conn=conn, cursor=cursor, prm=prm, jg=jg, threshold=args.threshold, capital=capital
        )
        print("\n" + "=" * 60)
        print(f"A. {args.threshold}件以上の日のみ（1日1ポジション想定・重複無視）")
        print("=" * 60)
        summarize(etf8, f"ETF {int(capital)//10000}万")
        summarize(stk8, f"個別1〜2銘柄 {int(capital)//10000}万")
        diff_a = sum(t.pnl for t in etf8) - sum(t.pnl for t in stk8)
        print(f"\n  → ETF - 個別 = {diff_a:+,}円（プラスならETF優位）")
        print_worst_best(etf8, "ETF")
        print_worst_best(stk8, "個別")

        print("\n" + "=" * 60)
        print("B. 10年フル（同時1ポジション・保有中はスキップ）")
        print("=" * 60)
        hybrid = run_portfolio(
            by_day, mode="hybrid", conn=conn, cursor=cursor, prm=prm, jg=jg,
            threshold=args.threshold, capital=capital,
        )
        always = run_portfolio(
            by_day, mode="always_stock", conn=conn, cursor=cursor, prm=prm, jg=jg,
            threshold=args.threshold, capital=capital,
        )
        summarize(hybrid, "ハイブリッド（8+→ETF / 未満→個別1-2）")
        summarize(always, "常に個別1-2")
        diff_b = sum(t.pnl for t in hybrid) - sum(t.pnl for t in always)
        print(f"\n  → ハイブリッド - 常に個別 = {diff_b:+,}円")

        if args.output:
            payload = {
                "capital": int(capital),
                "threshold": args.threshold,
                "independent_8plus": {
                    "etf": [t.__dict__ for t in etf8],
                    "stock": [t.__dict__ for t in stk8],
                },
                "portfolio_10y": {
                    "hybrid": [t.__dict__ for t in hybrid],
                    "always_stock": [t.__dict__ for t in always],
                },
            }
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"\nJSON: {out_path}")
    finally:
        db.close_db(conn)


if __name__ == "__main__":
    main()
