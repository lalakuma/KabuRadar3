"""5日移動平均線への接近利確判定."""

from __future__ import annotations

import math

MA5_MODE_OFFSET = "offset"
MA5_MODE_BAND = "band"
MA5_MODE_PULLBACK = "pullback"


def high_reached_ma5_offset(high: float, sma5: float, offset_pct: float) -> bool:
    """高値が5日線+offset%以上まで上がったか.

    offset=-1.0 なら高値 >= 5日線×0.99（5日線より1%下まで到達で利確）。
    sma5 は前日終値までで確定した5日線（当日終値を含めない）を渡すこと。
    """
    if sma5 <= 0 or math.isnan(sma5) or math.isnan(high):
        return False
    return high >= sma5 * (1 + offset_pct / 100.0)


def high_near_ma5(high: float, sma5: float, proximity_pct: float) -> bool:
    """高値が5日線の±proximity%帯に入ったか."""
    if sma5 <= 0 or math.isnan(sma5) or math.isnan(high):
        return False
    band = proximity_pct / 100.0
    lower = sma5 * (1 - band)
    upper = sma5 * (1 + band)
    return lower <= high <= upper


def rally_above_ma5(close: float, sma5: float, rally_pct: float) -> bool:
    """終値が5日線を一定割合上回ったか（押し目モード用）."""
    if sma5 <= 0 or math.isnan(sma5) or math.isnan(close):
        return False
    return close > sma5 * (1 + rally_pct / 100.0)


def near_ma5(close: float, low: float, sma5: float, proximity_pct: float) -> bool:
    """終値または安値が5日線の近傍帯に入ったか（押し目モード用）."""
    if sma5 <= 0 or math.isnan(sma5):
        return False
    band = proximity_pct / 100.0
    lower = sma5 * (1 - band)
    upper = sma5 * (1 + band)
    close_near = not math.isnan(close) and lower <= close <= upper
    low_touched = not math.isnan(low) and lower <= low <= upper
    return close_near or low_touched
