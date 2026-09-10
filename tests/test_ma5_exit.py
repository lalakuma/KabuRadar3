from __future__ import annotations

from kaburadar3.strategy.ma5 import (
    closed_below_ma5,
    entry_above_ma5,
    high_near_ma5,
    high_reached_ma5_offset,
    near_ma5,
    rally_above_ma5,
)


def test_high_reached_ma5_offset() -> None:
    assert high_reached_ma5_offset(990, 1000, -1.0) is True
    assert high_reached_ma5_offset(985, 1000, -1.0) is False
    assert high_reached_ma5_offset(1000, 1000, 0.0) is True


def test_high_near_ma5_band() -> None:
    assert high_near_ma5(1005, 1000, 1.5) is True
    assert high_near_ma5(980, 1000, 1.5) is False


def test_pullback_helpers() -> None:
    assert rally_above_ma5(1020, 1000, 1.0) is True
    assert near_ma5(1005, 995, 1000, 1.5) is True


def test_entry_above_and_ma5_break() -> None:
    assert entry_above_ma5(1010, 1000) is True
    assert entry_above_ma5(990, 1000) is False
    assert closed_below_ma5(990, 1000) is True
    assert closed_below_ma5(1000, 1000) is False
