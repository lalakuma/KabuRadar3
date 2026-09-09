"""5日移動平均線への接近利確判定."""

from __future__ import annotations

import math


def rally_above_ma5(close: float, sma5: float, rally_pct: float) -> bool:
    """終値が5日線を一定割合上回ったか（戻り確認）."""
    if sma5 <= 0 or math.isnan(sma5) or math.isnan(close):
        return False
    return close > sma5 * (1 + rally_pct / 100.0)


def near_ma5(close: float, low: float, sma5: float, proximity_pct: float) -> bool:
    """終値または安値が5日線の近傍帯に入ったか.

    戻り後の押し目で5日線付近まで近づいたタイミングを検出する。
    """
    if sma5 <= 0 or math.isnan(sma5):
        return False
    band = proximity_pct / 100.0
    lower = sma5 * (1 - band)
    upper = sma5 * (1 + band)
    close_near = not math.isnan(close) and lower <= close <= upper
    low_touched = not math.isnan(low) and lower <= low <= upper
    return close_near or low_touched
