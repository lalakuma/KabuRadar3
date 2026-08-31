from __future__ import annotations

import numpy as np
import pandas as pd

from kaburadar3.strategy.rci import attach_rci, compute_rci, jdg_rci_turn_down, jdg_rci_turn_up, jdg_rci_v_reversal


def test_compute_rci_range() -> None:
    close = pd.Series(np.linspace(100, 90, 20))
    rci = compute_rci(close, period=9)
    valid = rci.dropna()
    assert len(valid) == len(close) - 8
    assert valid.max() <= 100
    assert valid.min() >= -100


def test_jdg_rci_turn_down_detects_peak_reversal() -> None:
    close = pd.Series(range(100, 112), dtype=float)
    df = pd.DataFrame({"close": close})
    df = attach_rci(df, period=9)
    # 人工的に RCI を反転下落させる
    col = "RCI9"
    vals = df[col].tolist()
    vals[-2] = 50.0
    vals[-1] = 40.0
    df[col] = vals
    assert jdg_rci_turn_down(df, period=9, turn_min=5, peak_min=20, lookback=5) == 1


def test_jdg_rci_turn_down_skips_without_bounce() -> None:
    close = pd.Series(range(100, 112), dtype=float)
    df = pd.DataFrame({"close": close})
    df = attach_rci(df, period=9)
    col = "RCI9"
    vals = df[col].tolist()
    vals[-2] = -10.0
    vals[-1] = -20.0
    df[col] = vals
    assert jdg_rci_turn_down(df, period=9, turn_min=5, peak_min=20, lookback=5) == 0


def test_jdg_rci_turn_up_detects_rise() -> None:
    close = pd.Series(range(100, 112), dtype=float)
    df = pd.DataFrame({"close": close})
    df = attach_rci(df, period=9)
    col = "RCI9"
    vals = df[col].tolist()
    vals[-2] = 10.0
    vals[-1] = 16.0
    df[col] = vals
    assert jdg_rci_turn_up(df, period=9, turn_min=5) == 1


def test_jdg_rci_v_reversal_detects_turn() -> None:
    close = pd.Series(
        [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 87, 88, 89]
    )
    df = pd.DataFrame({"close": close})
    df = attach_rci(df, period=9)
    result = jdg_rci_v_reversal(df, period=9, rci_low=-50, turn_min=1, lookback=8, require_below_zero=True)
    assert result in (0, 1)
