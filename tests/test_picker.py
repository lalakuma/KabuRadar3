from __future__ import annotations

from kaburadar3.signals.picker import (
    PICK_CODE,
    PICK_RCI_RSI,
    PICK_RSI_LOW,
    PICK_STARS,
    pick_recommended,
)
from kaburadar3.signals.picker import attach_recommended_picks  # noqa: F401


def test_pick_rci_rsi_prefers_turn_and_low_rsi() -> None:
    signals = [
        {"code": "1001", "close": 1000, "rsi": 12.0, "rci_turn": False},
        {"code": "1002", "close": 2000, "rsi": 8.0, "rci_turn": True},
        {"code": "1003", "close": 1500, "rsi": 15.0, "rci_turn": True},
    ]
    picked = pick_recommended(signals, n=2, method=PICK_RCI_RSI)
    codes = [p["code"] for p in picked]
    assert codes[0] == "1002"
    assert len(picked) == 2


def test_pick_stars_excludes_low() -> None:
    signals = [
        {"code": "1001", "close": 1000, "rsi": 5.0, "quality": {"stars": 2}},
        {"code": "1002", "close": 2000, "rsi": 8.0, "quality": {"stars": 5}},
        {"code": "1003", "close": 1500, "rsi": 6.0, "quality": {"stars": 4}},
        {"code": "1004", "close": 1200, "rsi": 4.0, "quality": {"stars": 3}},
    ]
    picked = pick_recommended(signals, n=2, method=PICK_STARS, min_stars=4)
    codes = [p["code"] for p in picked]
    assert "1001" not in codes
    assert "1004" not in codes
    assert codes == ["1002", "1003"]


def test_pick_rsi_low() -> None:
    signals = [
        {"code": "1001", "close": 1000, "rsi": 12.0},
        {"code": "1002", "close": 2000, "rsi": 5.0},
    ]
    picked = pick_recommended(signals, n=1, method=PICK_RSI_LOW)
    assert picked[0]["code"] == "1002"


def test_pick_code_order() -> None:
    signals = [
        {"code": "2001", "close": 1000},
        {"code": "1001", "close": 1000},
    ]
    picked = pick_recommended(signals, n=1, method=PICK_CODE)
    assert picked[0]["code"] == "1001"


def test_attach_recommended_skips_etf_routing() -> None:
    from types import SimpleNamespace

    from kaburadar3.signals.picker import attach_recommended_picks

    today = {"new_buy": [{"code": "7203", "close": 2500}]}
    special = {"routing": "etf"}
    runtime = SimpleNamespace(pick_method=PICK_RCI_RSI, pick_count=2, pick_min_stars=3)
    attach_recommended_picks(today, special, runtime)
    assert today["recommended"] == []
