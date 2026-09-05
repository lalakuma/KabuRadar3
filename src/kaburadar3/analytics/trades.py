"""解析結果 CSV からトレード（新買→返売）を抽出."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from kaburadar3.settings.encoding import read_csv

_CODE_CSV = re.compile(r"^code(\d+)", re.IGNORECASE)


def _row_date(row: pd.Series, idx: object) -> date | None:
    if "Index" in row.index and pd.notna(row.get("Index")):
        return pd.Timestamp(row["Index"]).date()
    if isinstance(idx, pd.Timestamp):
        return idx.date()
    return None


def extract_trades_from_csv(path: Path, code: str | None = None) -> list[dict]:
    """1銘柄 CSV からエントリー単位のトレードを返す。"""
    match = _CODE_CSV.match(path.name)
    if not match:
        return []
    symbol = code or match.group(1)
    df = read_csv(path)
    if df.empty or "mark" not in df.columns:
        return []

    trades: list[dict] = []
    entry_date: date | None = None
    buy_price = 0.0
    hold_days = 0

    for idx, row in df.iterrows():
        mark = str(row.get("mark", "")).strip()
        if mark == "新買":
            entry_date = _row_date(row, idx)
            buy_price = float(row.get("close", 0) or 0)
            hold_days = 0
        elif mark == "継続" and entry_date is not None:
            hold_days += 1
        elif mark == "返売" and entry_date is not None:
            hold_days += 1
            exit_date = _row_date(row, idx)
            gain = int(row.get("buygain", 0) or 0)
            trades.append(
                {
                    "code": symbol,
                    "entry": entry_date.isoformat(),
                    "exit": exit_date.isoformat() if exit_date else None,
                    "buy_price": int(buy_price),
                    "exit_price": int(row.get("close", 0) or 0),
                    "gain": gain,
                    "hold_days": hold_days,
                    "closed": True,
                }
            )
            entry_date = None
            buy_price = 0.0
            hold_days = 0

    if entry_date is not None:
        trades.append(
            {
                "code": symbol,
                "entry": entry_date.isoformat(),
                "exit": None,
                "buy_price": int(buy_price),
                "exit_price": None,
                "gain": 0,
                "hold_days": hold_days,
                "closed": False,
            }
        )
    return trades


def extract_trades_from_results(results_dir: Path) -> list[dict]:
    """results フォルダ内の全 code*.csv からトレードを抽出。"""
    trades: list[dict] = []
    for path in sorted(results_dir.glob("code*.csv")):
        trades.extend(extract_trades_from_csv(path))
    return trades
