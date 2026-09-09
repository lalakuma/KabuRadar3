#!/usr/bin/env python3
"""ETF強制エントリー決済を日次キャッシュ（高速版）."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.analytics.backtest_report import infer_exit_reason
from kaburadar3.data import repository as db
from kaburadar3.domain import constants as DEF
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import engine, rci as tc_rci, rsi as tc_rsi
from kaburadar3.strategy.models import CodePrice, Judge, KabInf, TradeInfo

ETF_CODE = "1306"


def _load_etf_df(conn, cursor, start: date, end: date) -> pd.DataFrame:
    df = db.read_rec_period(conn, cursor, ETF_CODE, start.isoformat(), end.isoformat())
    if df is None or df.empty:
        return pd.DataFrame()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
    df["SMA5"] = df["close"].rolling(window=5).mean()
    df["SMA25"] = df["close"].rolling(window=25).mean()
    out = df.set_index("datetime").loc[:, ["open", "high", "low", "close", "volume", "SMA5", "SMA25"]]
    out = tc_rsi.rsi_tradingview(out, 4)
    jg = Judge(conf.CONF_SEC_SCR)
    return tc_rci.attach_rci(out, period=jg.rci_period)


def _simulate_from_idx(full: pd.DataFrame, entry_idx: int, *, prm: KabInf, jg: Judge) -> dict | None:
    if entry_idx >= len(full) or pd.isna(full.iloc[entry_idx]["SMA25"]):
        return None
    dates = [d.date() if hasattr(d, "date") else d for d in full.index]

    cp = CodePrice()
    cp.code = ETF_CODE
    ti = TradeInfo()
    ti.sb_mode = DEF.MODE_BUY
    buy_price = float(full.iloc[entry_idx]["close"])
    ti.buy_pos = 1
    ti.buy_price = buy_price

    cnt = 0
    for i in range(entry_idx + 1, len(full)):
        row = full.iloc[i]
        bkdf = full.iloc[: i + 1].reset_index(drop=True)
        cp.i_open = float(row["open"])
        cp.i_close = float(row["close"])
        cp.i_low = float(row["low"])
        cp.i_high = float(row["high"])
        cp.i_sma5 = float(row["SMA5"])
        cp.i_sma25 = float(row["SMA25"])
        cnt += 1
        exit_now, exit_price = engine._buy_exit_signal(cp, ti, jg, bkdf, prm, cnt)
        if not exit_now:
            continue
        exit_row = row.copy()
        exit_row["close"] = exit_price
        return {
            "entry": dates[entry_idx].isoformat(),
            "exit": dates[i].isoformat(),
            "buy_price": int(buy_price),
            "exit_price": int(exit_price),
            "hold_days": cnt,
            "exit_reason": infer_exit_reason(
                buy_price,
                exit_row,
                cnt,
                stop_pct=jg.stop_loss_pct,
                sell_period=prm.sell_period,
                rsi_hi=float(prm.srsi_hi),
            ),
        }
    return None


def build_etf_cache(
    entry_days: list[str],
    *,
    jg: Judge,
    prm: KabInf | None = None,
    conn=None,
    cursor=None,
) -> dict[str, dict]:
    if not entry_days:
        return {}
    if prm is None:
        scr = conf.CONF_SEC_SCR
        prm = KabInf(
            sell_period=int(conf.get_config(scr, conf.CONF_KEY_SCR_SELL_PERIOD)),
            srsi_hi=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_HI)),
            srsi_low=int(conf.get_config(scr, conf.CONF_KEY_SCR_SRSI_LOW)),
        )
    own = conn is None
    if own:
        conn, cursor = db.connect_db()
    assert cursor is not None

    parsed = [date.fromisoformat(d) for d in entry_days]
    start = min(parsed) - timedelta(days=120)
    end = max(parsed) + timedelta(days=prm.sell_period + 30)
    full = _load_etf_df(conn, cursor, start, end)
    if full.empty:
        if own:
            db.close_db(conn)
        return {}

    date_to_idx = {d.date() if hasattr(d, "date") else d: i for i, d in enumerate(full.index)}
    cache: dict[str, dict] = {}
    for day_s in entry_days:
        d = date.fromisoformat(day_s)
        if d not in date_to_idx:
            later = [x for x in date_to_idx if x >= d]
            if not later:
                continue
            d = min(later)
        r = _simulate_from_idx(full, date_to_idx[d], prm=prm, jg=jg)
        if r:
            cache[day_s] = r

    if own:
        db.close_db(conn)
    return cache
