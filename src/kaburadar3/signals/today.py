"""解析結果 CSV から当日の買い・返売りシグナルを抽出."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from kaburadar3.settings.encoding import read_csv
from kaburadar3.strategy import rci as tc_rci

MARK_NEW_BUY = "新買"
MARK_SELLBACK = "返売"
_CODE_CSV = re.compile(r"^code(\d+)", re.IGNORECASE)


def _row_trade_date(row: pd.Series, idx: object) -> pd.Timestamp | None:
    if "Index" in row.index and pd.notna(row["Index"]):
        return pd.Timestamp(row["Index"]).normalize()
    if isinstance(idx, pd.Timestamp):
        return idx.normalize()
    return None


def _parse_close(row: pd.Series) -> float | None:
    close_val = row.get("close")
    if pd.isna(close_val):
        return None
    close = float(close_val)
    if close <= 0:
        return None
    return close


def _read_code_last_row(path: Path) -> tuple[str, pd.Timestamp | None, str, float | None, dict] | None:
    """各銘柄 CSV の最終行 (code, date, mark, close, extras) を返す。"""
    df = read_csv(path)
    if df.empty or "mark" not in df.columns:
        return None
    match = _CODE_CSV.match(path.name)
    if not match:
        return None
    code = match.group(1)
    if "close" in df.columns:
        df = tc_rci.attach_rci(df, period=9)
    last = df.iloc[-1]
    mark = str(last.get("mark", "")).strip()
    dt = _row_trade_date(last, df.index[-1])
    close = _parse_close(last)
    extras: dict = {}
    for col in ("RSI4", "RCI9", "RSI"):
        if col in last.index and pd.notna(last.get(col)):
            key = "rci9" if col == "RCI9" else col.lower()
            extras[key] = float(last.get(col))
    if "rsi4" in extras:
        extras["rsi"] = extras["rsi4"]
    if "rci9" in extras and len(df) >= 2 and "RCI9" in df.columns:
        prev_rci = df["RCI9"].iloc[-2]
        now_rci = extras["rci9"]
        if pd.notna(prev_rci):
            extras["rci_turn"] = float(now_rci) > float(prev_rci)
    return code, dt, mark, close, extras


def collect_today_signals(
    results_dir: Path,
    name_map: dict[str, str] | None = None,
) -> dict:
    """最新営業日の最終バーに 新買・返売 がある銘柄だけ返す。"""
    name_map = name_map or {}
    last_rows: list[tuple[str, pd.Timestamp | None, str, float | None, dict]] = []
    for path in sorted(results_dir.glob("code*.csv")):
        row = _read_code_last_row(path)
        if row is not None:
            last_rows.append(row)

    trade_dates = [dt for _c, dt, _m, _cl, _ex in last_rows if dt is not None]
    if not trade_dates:
        return {
            "trade_date": None,
            "new_buy": [],
            "sellback": [],
            "new_buy_count": 0,
        }

    trade_date = max(trade_dates)
    trade_str = trade_date.strftime("%Y-%m-%d")

    def _to_item(code: str, mark: str, close: float | None, extras: dict | None = None) -> dict:
        item = {
            "code": code,
            "name": name_map.get(code, ""),
            "mark": mark,
        }
        if close is not None:
            item["close"] = int(round(close))
        extras = extras or {}
        if "rsi" in extras:
            item["rsi"] = round(extras["rsi"], 2)
        if "rci9" in extras:
            item["rci"] = round(extras["rci9"], 2)
            item["rci_turn"] = bool(extras.get("rci_turn", False))
        return item

    new_buy: list[dict] = []
    sellback: list[dict] = []
    for code, dt, mark, close, extras in last_rows:
        if dt != trade_date:
            continue
        if mark == MARK_NEW_BUY and close is not None:
            new_buy.append(_to_item(code, mark, close, extras))
        elif mark == MARK_SELLBACK and close is not None:
            sellback.append(_to_item(code, mark, close, extras))

    new_buy.sort(key=lambda x: x["code"])
    sellback.sort(key=lambda x: x["code"])
    return {
        "trade_date": trade_str,
        "new_buy": new_buy,
        "sellback": sellback,
        "new_buy_count": len(new_buy),
    }
