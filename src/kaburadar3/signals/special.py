"""広がり（新買件数）と地合いに基づく特別買いステートと ETF RSI 利確."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from kaburadar3.analytics.backtest_deep import load_market_closes, market_return_at
from kaburadar3.data import repository as db
from kaburadar3.settings.paths import DATA_DIR
from kaburadar3.settings.runtime import RuntimeConfig
from kaburadar3.strategy import rsi as tc_rsi

STATE_FILE = DATA_DIR / "special_state.json"
STATE_IDLE = "idle"
STATE_SPECIAL_LONG = "special_long"
ROUTING_ETF = "etf"
ROUTING_STOCKS = "stocks"

DEFAULT_STATE: dict[str, Any] = {
    "state": STATE_IDLE,
    "entered_on": None,
    "etf": None,
    "last_special_buy_notify": None,
    "last_special_exit_notify": None,
}


def evaluate_routing(
    new_buy_count: int,
    market_return_20d: float | None,
    runtime: RuntimeConfig,
) -> str:
    """8件以上かつ地合20日>=閾値なら ETF、それ以外は個別株."""
    if not runtime.special_buy_enabled:
        return ROUTING_STOCKS
    if new_buy_count < runtime.min_new_buy_count:
        return ROUTING_STOCKS
    if market_return_20d is None or market_return_20d >= runtime.market_regime_min_pct:
        return ROUTING_ETF
    return ROUTING_STOCKS


def load_special_state(path: Path | None = None) -> dict:
    target = path or STATE_FILE
    if not target.is_file():
        return deepcopy(DEFAULT_STATE)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return deepcopy(DEFAULT_STATE)
    merged = deepcopy(DEFAULT_STATE)
    if isinstance(data, dict):
        merged.update(data)
    return merged


def save_special_state(state: dict, path: Path | None = None) -> None:
    target = path or STATE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_rsi4(conn, cursor, code: str, lookback: int = 120) -> tuple[float | None, str | None]:
    end = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    start = (datetime.now(timezone.utc).astimezone() - pd.Timedelta(days=lookback * 2)).strftime(
        "%Y-%m-%d"
    )
    df = db.read_rec_period(conn, cursor, code, start, end)
    if df is None or len(df) < 5:
        return None, None
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime", "close"]).sort_values("datetime")
    if len(df) < 5:
        return None, None
    df = df.set_index("datetime")
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = tc_rsi.rsi_tradingview(df, period=4, round_rsi=True)
    last_dt = df.index[-1]
    rsi4 = float(df["RSI4"].iloc[-1])
    return rsi4, last_dt.strftime("%Y-%m-%d")


def _market_return_20d(
    trade_date: str,
    *,
    proxy_code: str,
    lookback: int,
    conn,
    cursor,
) -> float | None:
    if not trade_date:
        return None
    closes = load_market_closes(cursor, proxy_code)
    return market_return_at(closes, date.fromisoformat(trade_date), lookback=lookback)


def apply_special_buy(
    trade_date: str | None,
    new_buy_count: int,
    runtime: RuntimeConfig,
    state_path: Path | None = None,
) -> tuple[dict, dict, list[str]]:
    """特別買いロジックを適用し、(web用dict, 保存state, LINE行) を返す。"""
    state = load_special_state(state_path)
    lines: list[str] = []
    etf_rsi: dict[str, float | None] = {code: None for code in runtime.etf_codes}
    trade_date = trade_date or ""
    market_return_20d: float | None = None

    if runtime.special_buy_enabled and trade_date:
        conn, cursor = db.connect_db()
        try:
            market_return_20d = _market_return_20d(
                trade_date,
                proxy_code=runtime.etf_default,
                lookback=runtime.market_regime_lookback_days,
                conn=conn,
                cursor=cursor,
            )
            for code in runtime.etf_codes:
                rsi_val, _ = _latest_rsi4(conn, cursor, code)
                etf_rsi[code] = rsi_val
        finally:
            db.close_db(conn)

    routing = evaluate_routing(new_buy_count, market_return_20d, runtime)
    active_etf = state.get("etf") or runtime.etf_default
    current_rsi = etf_rsi.get(active_etf)
    day_signal: str | None = None
    mkt_text = f"{market_return_20d:+.1f}%" if market_return_20d is not None else "—"

    if (
        routing == ROUTING_ETF
        and state.get("state") == STATE_IDLE
        and trade_date
    ):
        state = {
            **state,
            "state": STATE_SPECIAL_LONG,
            "entered_on": trade_date,
            "etf": runtime.etf_default,
        }
        active_etf = runtime.etf_default
        current_rsi = etf_rsi.get(active_etf)
        day_signal = "buy"
        if runtime.notify_special_buy_on and state.get("last_special_buy_notify") != trade_date:
            lines.append(
                f"【ETF推奨】新買 {new_buy_count}件 / 地合{runtime.market_regime_lookback_days}日 {mkt_text}"
            )
            lines.append(
                f"ETF {runtime.etf_default}（東証指数）— 個別株は本日見送り"
            )
            state["last_special_buy_notify"] = trade_date

    elif (
        routing == ROUTING_STOCKS
        and new_buy_count >= runtime.min_new_buy_count
        and trade_date
        and runtime.notify_special_buy_on
        and state.get("last_special_buy_notify") != trade_date
    ):
        lines.append(
            f"【個別推奨】新買 {new_buy_count}件 / 地合{runtime.market_regime_lookback_days}日 {mkt_text}"
        )
        lines.append(
            f"地合 < {runtime.market_regime_min_pct:g}% のため ETF ではなく個別1〜2銘柄"
        )
        state["last_special_buy_notify"] = trade_date

    elif state.get("state") == STATE_SPECIAL_LONG and current_rsi is not None:
        if current_rsi >= runtime.exit_rsi:
            exit_key = f"{trade_date}:{active_etf}"
            day_signal = "sell"
            if runtime.notify_special_exit and state.get("last_special_exit_notify") != exit_key:
                lines.append(f"【特別買い 売り】{active_etf} RSI={current_rsi:.1f} >= {runtime.exit_rsi:g}")
                lines.append("利確シグナル")
                state["last_special_exit_notify"] = exit_key
            state = {
                **DEFAULT_STATE,
                "last_special_buy_notify": state.get("last_special_buy_notify"),
                "last_special_exit_notify": state.get("last_special_exit_notify"),
            }
        else:
            day_signal = "holding"

    special = {
        "enabled": runtime.special_buy_enabled,
        "state": state.get("state", STATE_IDLE),
        "entered_on": state.get("entered_on"),
        "etf": state.get("etf"),
        "routing": routing,
        "min_new_buy_count": runtime.min_new_buy_count,
        "market_regime_min_pct": runtime.market_regime_min_pct,
        "market_regime_lookback_days": runtime.market_regime_lookback_days,
        "market_return_20d": round(market_return_20d, 2) if market_return_20d is not None else None,
        "new_buy_count": new_buy_count,
        "exit_rsi": runtime.exit_rsi,
        "etf_rsi": {k: (round(v, 2) if v is not None else None) for k, v in etf_rsi.items()},
        "active_rsi": round(current_rsi, 2) if current_rsi is not None else None,
        "signal": day_signal,
    }

    save_special_state(state, state_path)
    return special, state, lines
