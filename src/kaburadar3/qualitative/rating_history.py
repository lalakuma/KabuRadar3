"""Gemini 星評価の時系列アーカイブ（signal_ratings.jsonl）."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kaburadar3.settings.paths import PROJECT_ROOT

HISTORY_FILE = PROJECT_ROOT / "data" / "signal_ratings.jsonl"


def _entry_key(trade_date: str, code: str) -> str:
    return f"{trade_date}:{code}"


def load_history(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or HISTORY_FILE
    if not target.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    return rows


def existing_keys(path: Path | None = None) -> set[str]:
    keys: set[str] = set()
    for row in load_history(path):
        date = str(row.get("date", "")).strip()
        code = str(row.get("code", "")).strip()
        if date and code:
            keys.add(_entry_key(date, code))
    return keys


def append_signal_ratings(
    trade_date: str,
    signals: list[dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
    model: str | None = None,
    path: Path | None = None,
) -> int:
    """publish 時に新規 (date, code) の評価を JSONL へ追記。追記件数を返す。"""
    if not trade_date or not ratings:
        return 0

    target = path or HISTORY_FILE
    known = existing_keys(target)
    lines: list[str] = []
    appended = 0

    for item in signals:
        code = str(item.get("code", "")).strip()
        if not code or code not in ratings:
            continue
        key = _entry_key(trade_date, code)
        if key in known:
            continue

        rating = ratings[code]
        record = {
            "date": trade_date,
            "code": code,
            "mark": str(item.get("mark") or "新買"),
            "stars": int(rating.get("stars", 3)),
            "confidence": str(rating.get("confidence", "medium")),
            "model": model or "",
        }
        lines.append(json.dumps(record, ensure_ascii=False))
        known.add(key)
        appended += 1

    if not lines:
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")
    return appended


def build_rating_lookup(
    cache: dict[str, dict[str, Any]] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """date:code -> rating dict。cache を優先し history で補完。"""
    lookup: dict[str, dict[str, Any]] = {}
    if history:
        for row in history:
            date = str(row.get("date", "")).strip()
            code = str(row.get("code", "")).strip()
            if not date or not code:
                continue
            lookup[_entry_key(date, code)] = {
                "stars": int(row.get("stars", 3)),
                "confidence": str(row.get("confidence", "medium")),
            }
    if cache:
        for key, value in cache.items():
            if isinstance(value, dict):
                lookup[key] = value
    return lookup


def attach_quality_to_daily(daily: dict[str, Any], cache: dict[str, dict[str, Any]]) -> None:
    """daily.days[].new_buy に cache から quality を付与（in-place）。"""
    from kaburadar3.qualitative.rater import _apply_fundamentals, _cache_key
    from kaburadar3.qualitative.schema import QualityRating

    for day in daily.get("days", []):
        date = str(day.get("date", "")).strip()
        if not date:
            continue
        for item in day.get("new_buy", []):
            code = str(item.get("code", "")).strip()
            if not code:
                continue
            cached = cache.get(_cache_key(code, date)) or cache.get(_entry_key(date, code))
            if cached:
                rating = _apply_fundamentals(QualityRating.from_dict(cached), code)
                item["quality"] = rating.to_dict()
