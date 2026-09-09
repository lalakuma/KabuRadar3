from __future__ import annotations

from kaburadar3.strategy.ma5 import near_ma5, rally_above_ma5


def test_rally_above_ma5() -> None:
    assert rally_above_ma5(1020, 1000, 1.0) is True
    assert rally_above_ma5(1005, 1000, 1.0) is False


def test_near_ma5_by_close() -> None:
    assert near_ma5(1005, 995, 1000, 1.5) is True
    assert near_ma5(1030, 1020, 1000, 1.5) is False


def test_near_ma5_by_low_touch() -> None:
    assert near_ma5(1020, 1005, 1000, 1.5) is True
