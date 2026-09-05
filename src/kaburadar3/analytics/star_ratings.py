"""星評価（★1-5）とトレード結果の結合・集計."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MIN_TOTAL_CLOSED = 30
MIN_TIER_CLOSED = 10


@dataclass
class StrategyStats:
    name: str
    entries: int
    closed: int
    open_count: int
    wins: int
    losses: int
    win_rate: float | None
    pf: float | None
    total_gain: int
    avg_gain: float | None


def _calc_stats(name: str, rows: list[dict]) -> StrategyStats:
    closed = [r for r in rows if r.get("closed")]
    open_rows = [r for r in rows if not r.get("closed")]
    wins = [r for r in closed if int(r.get("gain", 0)) > 0]
    losses = [r for r in closed if int(r.get("gain", 0)) < 0]
    total_gain = sum(int(r.get("gain", 0)) for r in closed)
    plus = sum(int(r.get("gain", 0)) for r in wins)
    minus = sum(int(r.get("gain", 0)) for r in losses)
    pf = plus / abs(minus) if minus else (plus if plus else None)
    wr = len(wins) / len(closed) * 100 if closed else None
    avg = total_gain / len(closed) if closed else None
    return StrategyStats(
        name=name,
        entries=len(rows),
        closed=len(closed),
        open_count=len(open_rows),
        wins=len(wins),
        losses=len(losses),
        win_rate=round(wr, 1) if wr is not None else None,
        pf=round(pf, 2) if pf is not None else None,
        total_gain=total_gain,
        avg_gain=round(avg, 1) if avg is not None else None,
    )


def join_trades_with_ratings(
    trades: list[dict],
    rating_lookup: dict[str, dict[str, Any]],
) -> tuple[list[dict], list[dict]]:
    """新買エントリーに星評価を付与。 (matched, unmatched) を返す。"""
    matched: list[dict] = []
    unmatched: list[dict] = []
    for trade in trades:
        key = f"{trade['entry']}:{trade['code']}"
        rating = rating_lookup.get(key)
        row = dict(trade)
        if rating:
            row["stars"] = int(rating.get("stars", 3))
            row["confidence"] = str(rating.get("confidence", "medium"))
            matched.append(row)
        else:
            unmatched.append(row)
    return matched, unmatched


def tier_stats(matched: list[dict]) -> list[dict[str, Any]]:
    """星 tier 別の集計。"""
    by_star: dict[int, list[dict]] = {}
    for row in matched:
        stars = int(row.get("stars", 0))
        by_star.setdefault(stars, []).append(row)

    out: list[dict[str, Any]] = []
    for stars in sorted(by_star):
        stats = _calc_stats(f"★{stars}", by_star[stars])
        item = asdict(stats)
        item["stars"] = stars
        item["sample_ok"] = stats.closed >= MIN_TIER_CLOSED
        out.append(item)
    return out


def compare_strategies(matched: list[dict]) -> list[dict[str, Any]]:
    """フィルター戦略の比較。"""
    strategies = [
        ("baseline", lambda r: True),
        ("stars_4_5", lambda r: int(r.get("stars", 0)) >= 4),
        ("exclude_1_2", lambda r: int(r.get("stars", 0)) >= 3),
        ("stars_5_only", lambda r: int(r.get("stars", 0)) == 5),
    ]
    return [asdict(_calc_stats(name, [r for r in matched if pred(r)])) for name, pred in strategies]


def analyze_star_ratings(
    trades: list[dict],
    rating_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """星評価バックテストのレポート dict を生成。"""
    matched, unmatched = join_trades_with_ratings(trades, rating_lookup)
    closed_matched = [r for r in matched if r.get("closed")]
    report: dict[str, Any] = {
        "summary": {
            "total_entries": len(trades),
            "rated_entries": len(matched),
            "unrated_entries": len(unmatched),
            "closed_rated": len(closed_matched),
            "sample_sufficient": len(closed_matched) >= MIN_TOTAL_CLOSED,
            "min_total_closed": MIN_TOTAL_CLOSED,
            "min_tier_closed": MIN_TIER_CLOSED,
        },
        "by_stars": tier_stats(matched),
        "strategies": compare_strategies(matched),
        "unmatched_closed": len([r for r in unmatched if r.get("closed")]),
    }
    return report
