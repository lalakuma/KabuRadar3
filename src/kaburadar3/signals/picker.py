"""新買シグナルから実運用向けに1〜2銘柄を選定."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from kaburadar3.data import repository as db
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import rci as tc_rci
from kaburadar3.strategy import rsi as tc_rsi
from kaburadar3.strategy.models import Judge

ETF_CODE = "1306"

PICK_CODE = "code"
PICK_RSI_LOW = "rsi_low"
PICK_RCI_RSI = "rci_rsi"
PICK_STARS = "stars"

DEFAULT_METHOD = PICK_STARS
DEFAULT_COUNT = 2
DEFAULT_MIN_STARS = 4


def _stars(item: dict[str, Any]) -> int:
    quality = item.get("quality") or {}
    try:
        return int(quality.get("stars", 3))
    except (TypeError, ValueError):
        return 3


def _rsi(item: dict[str, Any]) -> float:
    val = item.get("rsi")
    if val is None:
        return 50.0
    return float(val)


def _rci(item: dict[str, Any]) -> float:
    val = item.get("rci")
    if val is None:
        return 0.0
    return float(val)


def _rci_turn(item: dict[str, Any]) -> bool:
    return bool(item.get("rci_turn"))


def _close(item: dict[str, Any]) -> float:
    for key in ("close", "buy_price"):
        val = item.get(key)
        if val is not None:
            return float(val)
    return 0.0


def _fits_capital(item: dict[str, Any], capital: float) -> bool:
    close = _close(item)
    return close > 0 and close * 100 <= capital


def pick_recommended(
    signals: list[dict[str, Any]],
    *,
    n: int = DEFAULT_COUNT,
    method: str = DEFAULT_METHOD,
    min_stars: int = DEFAULT_MIN_STARS,
    capital: float = 500_000,
    exclude_etf: bool = True,
) -> list[dict[str, Any]]:
    """新買リストから最大 n 銘柄を選ぶ."""
    rows = [dict(s) for s in signals if s.get("closed", True)]
    if exclude_etf:
        rows = [r for r in rows if str(r.get("code", "")) != ETF_CODE]

    if method == PICK_STARS:
        rows = [r for r in rows if _stars(r) >= min_stars]
        rows.sort(key=lambda r: (-_stars(r), _rsi(r), str(r.get("code", ""))))
    elif method == PICK_RSI_LOW:
        rows.sort(key=lambda r: (_rsi(r), str(r.get("code", ""))))
    elif method == PICK_RCI_RSI:
        rows.sort(
            key=lambda r: (
                0 if _rci_turn(r) else 1,
                _rsi(r),
                str(r.get("code", "")),
            )
        )
    else:
        rows.sort(key=lambda r: str(r.get("code", "")))

    affordable = [r for r in rows if _fits_capital(r, capital)]
    pool = affordable if affordable else rows
    return pool[: max(1, n)]


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame | None:
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime", "close"]).sort_values("datetime")
    if len(df) < 5:
        return None
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.set_index("datetime")
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df = tc_rsi.rsi_tradingview(df, period=4)
    jg = Judge(conf.CONF_SEC_SCR)
    return tc_rci.attach_rci(df, period=jg.rci_period)


def _lookup_ts(df: pd.DataFrame, entry: date) -> pd.Timestamp | None:
    target = pd.Timestamp(entry)
    if target in df.index:
        return target
    later = df.index[df.index >= target]
    if len(later) == 0:
        return None
    return later[0]


def _row_to_extras(df: pd.DataFrame, target: pd.Timestamp) -> dict[str, Any]:
    row = df.loc[target]
    idx = df.index.get_loc(target)
    rsi = float(row.get("RSI4", 50))
    rci = float(row.get("RCI9", 0))
    rci_turn = False
    if idx > 0 and "RCI9" in df.columns:
        rci_turn = float(df["RCI9"].iloc[idx]) > float(df["RCI9"].iloc[idx - 1])
    return {
        "rsi": round(rsi, 2),
        "rci": round(rci, 2),
        "rci_turn": rci_turn,
    }


def indicators_at_entry(conn, cursor, code: str, entry: date) -> dict[str, Any]:
    """エントリー日の RSI4 / RCI9 / rci_turn を DB から取得."""
    start = (entry - timedelta(days=120)).isoformat()
    end = (entry + timedelta(days=5)).isoformat()
    df = db.read_rec_period(conn, cursor, str(code), start, end)
    if df is None or df.empty:
        return {}
    prepared = _prepare_df(df)
    if prepared is None:
        return {}
    target = _lookup_ts(prepared, entry)
    if target is None:
        return {}
    row = prepared.loc[target]
    extras = _row_to_extras(prepared, target)
    extras["close"] = int(row["close"])
    return extras


def enrich_trades_by_code(
    trades: list[dict[str, Any]],
    conn,
    cursor,
) -> list[dict[str, Any]]:
    """バックテスト trades にエントリー日テクニカルを付与（銘柄ごとに一括）."""
    by_code: dict[str, list[dict[str, Any]]] = {}
    for t in trades:
        by_code.setdefault(str(t["code"]), []).append(t)

    cache: dict[tuple[str, str], dict[str, Any]] = {}
    out: list[dict[str, Any]] = []

    for code, code_trades in by_code.items():
        if code == ETF_CODE:
            for t in code_trades:
                out.append({**t, "closed": t.get("closed", True)})
            continue

        start = min(date.fromisoformat(t["entry"][:10]) for t in code_trades)
        end = max(date.fromisoformat(t["entry"][:10]) for t in code_trades)
        df_start = (start - timedelta(days=120)).isoformat()
        df_end = (end + timedelta(days=5)).isoformat()
        df = db.read_rec_period(conn, cursor, code, df_start, df_end)
        if df is None or df.empty:
            for t in code_trades:
                out.append({**t, "closed": t.get("closed", True)})
            continue

        prepared = _prepare_df(df)
        if prepared is None:
            for t in code_trades:
                out.append({**t, "closed": t.get("closed", True)})
            continue

        for t in code_trades:
            entry = t["entry"][:10]
            key = (code, entry)
            if key not in cache:
                target = _lookup_ts(prepared, date.fromisoformat(entry))
                cache[key] = _row_to_extras(prepared, target) if target is not None else {}
            merged = {**t, **cache.get(key, {}), "closed": t.get("closed", True)}
            out.append(merged)

    return out


def trades_to_signal(trade: dict[str, Any]) -> dict[str, Any]:
    """バックテスト trade 行を pick_recommended 向け dict に."""
    return {
        "code": str(trade["code"]),
        "buy_price": trade.get("buy_price"),
        "close": trade.get("buy_price"),
        "rsi": trade.get("rsi"),
        "rci": trade.get("rci"),
        "rci_turn": trade.get("rci_turn"),
        "quality": trade.get("quality"),
        "closed": trade.get("closed", True),
        "_trade": trade,
    }


def pick_trades(
    day_trades: list[dict[str, Any]],
    *,
    n: int = DEFAULT_COUNT,
    method: str = DEFAULT_METHOD,
    min_stars: int = DEFAULT_MIN_STARS,
    capital: float = 500_000,
) -> list[dict[str, Any]]:
    """エントリー日の trades から元 trade dict を返す."""
    signals = [trades_to_signal(t) for t in day_trades if t.get("closed")]
    picked = pick_recommended(
        signals, n=n, method=method, min_stars=min_stars, capital=capital
    )
    out: list[dict[str, Any]] = []
    for p in picked:
        src = p.get("_trade")
        if src:
            out.append(src)
    return out


def attach_recommended_picks(
    today: dict[str, Any],
    special: dict[str, Any],
    runtime: Any,
    *,
    capital: float = 500_000,
) -> None:
    """today に recommended / pick_meta を付与（routing=etf の日は空）."""
    routing = special.get("routing", "stocks")
    method = getattr(runtime, "pick_method", DEFAULT_METHOD)
    n = getattr(runtime, "pick_count", DEFAULT_COUNT)
    min_stars = getattr(runtime, "pick_min_stars", DEFAULT_MIN_STARS)

    if routing == "etf":
        today["recommended"] = []
        today["pick_meta"] = {
            "method": method,
            "routing": routing,
            "reason": "ETF推奨日のため個別自動選定なし",
        }
        return

    buys = list(today.get("new_buy") or [])
    recommended = pick_recommended(
        buys,
        n=n,
        method=method,
        min_stars=min_stars,
        capital=capital,
        exclude_etf=True,
    )
    for item in recommended:
        item["recommended"] = True
    today["recommended"] = recommended
    today["pick_meta"] = {
        "method": method,
        "routing": routing,
        "count": len(recommended),
        "min_stars": min_stars,
    }
