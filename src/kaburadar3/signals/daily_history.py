"""解析結果 CSV から日付別のシグナル・損益履歴を抽出."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from kaburadar3.settings.encoding import read_csv
from kaburadar3.signals.today import MARK_NEW_BUY, MARK_SELLBACK, _CODE_CSV, _parse_close, _row_trade_date

DEFAULT_MAX_DAYS = 60


def _row_pnl(row: pd.Series) -> int:
    buy = row.get("buygain")
    sell = row.get("sellgain")
    buy_v = int(buy) if pd.notna(buy) else 0
    sell_v = int(sell) if pd.notna(sell) else 0
    return buy_v + sell_v


def _to_signal_item(code: str, mark: str, close: float | None, pnl: int, name_map: dict[str, str]) -> dict:
    item: dict = {
        "code": code,
        "name": name_map.get(code, ""),
        "mark": mark,
    }
    if close is not None:
        item["close"] = int(round(close))
    if pnl != 0:
        item["pnl"] = pnl
    return item


def collect_daily_history(
    results_dir: Path,
    name_map: dict[str, str] | None = None,
    max_days: int = DEFAULT_MAX_DAYS,
) -> dict:
    """直近 max_days 営業日分の新買・返売りと日次損益を返す。"""
    name_map = name_map or {}
    by_date: dict[pd.Timestamp, dict] = defaultdict(
        lambda: {"pnl": 0, "new_buy": [], "sellback": []},
    )

    for path in sorted(results_dir.glob("code*.csv")):
        match = _CODE_CSV.match(path.name)
        if not match:
            continue
        code = match.group(1)
        df = read_csv(path)
        if df.empty or "mark" not in df.columns:
            continue

        for idx, row in df.iterrows():
            dt = _row_trade_date(row, idx)
            if dt is None:
                continue
            pnl = _row_pnl(row)
            mark = str(row.get("mark", "")).strip()
            close = _parse_close(row)

            bucket = by_date[dt]
            bucket["pnl"] += pnl

            if mark == MARK_NEW_BUY and close is not None:
                bucket["new_buy"].append(_to_signal_item(code, mark, close, pnl, name_map))
            elif mark == MARK_SELLBACK and close is not None:
                bucket["sellback"].append(_to_signal_item(code, mark, close, pnl, name_map))

    if not by_date:
        return {"days": [], "buy_days": []}

    sorted_dates = sorted(by_date.keys(), reverse=True)[:max_days]
    days: list[dict] = []
    for dt in sorted_dates:
        bucket = by_date[dt]
        new_buy = sorted(bucket["new_buy"], key=lambda x: x["code"])
        sellback = sorted(bucket["sellback"], key=lambda x: x["code"])
        days.append(
            {
                "date": dt.strftime("%Y-%m-%d"),
                "pnl": bucket["pnl"],
                "new_buy_count": len(new_buy),
                "sellback_count": len(sellback),
                "new_buy": new_buy,
                "sellback": sellback,
            },
        )
    buy_days = [d for d in days if d["new_buy_count"] > 0]
    return {"days": days, "buy_days": buy_days}
