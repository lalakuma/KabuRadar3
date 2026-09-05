from __future__ import annotations

import json
from pathlib import Path

from kaburadar3.analytics.star_ratings import analyze_star_ratings
from kaburadar3.analytics.trades import extract_trades_from_csv
from kaburadar3.qualitative.rating_history import (
    append_signal_ratings,
    attach_quality_to_daily,
    build_rating_lookup,
    existing_keys,
    load_history,
)
from kaburadar3.settings.encoding import CSV_ENCODING


def test_append_signal_ratings_dedupes(tmp_path: Path) -> None:
    path = tmp_path / "signal_ratings.jsonl"
    signals = [{"code": "1000", "mark": "新買"}]
    ratings = {"1000": {"stars": 4, "confidence": "high"}}
    assert append_signal_ratings("2026-09-02", signals, ratings, model="test", path=path) == 1
    assert append_signal_ratings("2026-09-02", signals, ratings, model="test", path=path) == 0
    assert len(load_history(path)) == 1
    assert existing_keys(path) == {"2026-09-02:1000"}


def test_attach_quality_to_daily() -> None:
    daily = {
        "days": [
            {
                "date": "2026-09-02",
                "new_buy": [{"code": "2670", "name": "エービーシー"}],
            }
        ]
    }
    cache = {"2026-09-02:2670": {"stars": 4, "background": "test"}}
    attach_quality_to_daily(daily, cache)
    assert daily["days"][0]["new_buy"][0]["quality"]["stars"] == 4


def test_extract_trades_from_csv(tmp_path: Path) -> None:
    csv = tmp_path / "code1000_rsi.csv"
    csv.write_text(
        "Index,mark,close,buygain\n"
        "2026-06-01,新買,1000,0\n"
        "2026-06-03,返売,1100,5000\n"
        "2026-06-10,新買,900,0\n",
        encoding=CSV_ENCODING,
    )
    trades = extract_trades_from_csv(csv)
    assert len(trades) == 2
    assert trades[0]["closed"] is True
    assert trades[0]["gain"] == 5000
    assert trades[1]["closed"] is False


def test_analyze_star_ratings_by_tier(tmp_path: Path) -> None:
    csv = tmp_path / "code1000_rsi.csv"
    csv.write_text(
        "Index,mark,close,buygain\n"
        "2026-06-01,新買,1000,0\n"
        "2026-06-03,返売,1100,5000\n"
        "2026-06-10,新買,900,0\n"
        "2026-06-12,返売,800,-2000\n",
        encoding=CSV_ENCODING,
    )
    trades = extract_trades_from_csv(csv)
    lookup = {
        "2026-06-01:1000": {"stars": 5, "confidence": "high"},
        "2026-06-10:1000": {"stars": 2, "confidence": "medium"},
    }
    report = analyze_star_ratings(trades, lookup)
    assert report["summary"]["rated_entries"] == 2
    assert report["summary"]["closed_rated"] == 2
    assert len(report["by_stars"]) == 2
    baseline = next(s for s in report["strategies"] if s["name"] == "baseline")
    stars_45 = next(s for s in report["strategies"] if s["name"] == "stars_4_5")
    assert baseline["closed"] == 2
    assert stars_45["closed"] == 1
    assert stars_45["total_gain"] == 5000


def test_build_rating_lookup_prefers_cache() -> None:
    history = [{"date": "2026-09-01", "code": "1000", "stars": 3, "confidence": "low"}]
    cache = {"2026-09-01:1000": {"stars": 5, "confidence": "high"}}
    lookup = build_rating_lookup(cache=cache, history=history)
    assert lookup["2026-09-01:1000"]["stars"] == 5
