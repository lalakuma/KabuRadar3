from __future__ import annotations

from kaburadar3.strategy.ma5 import high_near_ma5


def test_high_near_ma5_in_band() -> None:
    assert high_near_ma5(1005, 1000, 1.5) is True
    assert high_near_ma5(1010, 1000, 1.5) is True


def test_high_near_ma5_not_reached() -> None:
    assert high_near_ma5(980, 1000, 1.5) is False


def test_high_near_ma5_overshoot() -> None:
    assert high_near_ma5(1030, 1000, 1.5) is False
