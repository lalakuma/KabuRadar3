"""5日移動平均線への接近利確判定."""

from __future__ import annotations

import math


def high_near_ma5(high: float, sma5: float, proximity_pct: float) -> bool:
    """高値が5日線の近傍帯まで上がったか.

    エントリー後（多くは5日線下）の戻りで、高値が5日線付近に到達したタイミングを検出する。
    """
    if sma5 <= 0 or math.isnan(sma5) or math.isnan(high):
        return False
    band = proximity_pct / 100.0
    lower = sma5 * (1 - band)
    upper = sma5 * (1 + band)
    return lower <= high <= upper
