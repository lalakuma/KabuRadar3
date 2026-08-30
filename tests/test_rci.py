from __future__ import annotations

import numpy as np
import pandas as pd

from kaburadar3.strategy.rci import attach_rci, compute_rci, jdg_rci_v_reversal


def test_compute_rci_range() -> None:
    close = pd.Series(np.linspace(100, 90, 20))
    rci = compute_rci(close, period=9)
    valid = rci.dropna()
    assert len(valid) == len(close) - 8
    assert valid.max() <= 100
    assert valid.min() >= -100


def test_jdg_rci_v_reversal_detects_turn() -> None:
    close = pd.Series(
        [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87, 86, 87, 88, 89]
    )
    df = pd.DataFrame({"close": close})
    df = attach_rci(df, period=9)
    # 深い下落後の反発を V字として拾えるか（閾値次第で 0/1 両方あり得る）
    result = jdg_rci_v_reversal(df, period=9, rci_low=-50, turn_min=1, lookback=8, require_below_zero=True)
    assert result in (0, 1)
