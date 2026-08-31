"""RCI (Rank Correlation Index) と V字反転（底打ち）判定."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rci(close: pd.Series, period: int = 9) -> pd.Series:
    """終値系列から RCI (-100〜100) を計算する。"""
    if period < 2:
        raise ValueError("period must be >= 2")

    values = close.astype(float).values
    out = np.full(len(values), np.nan, dtype=float)
    time_ranks = np.arange(period, 0, -1, dtype=float)

    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        if np.any(np.isnan(window)):
            continue
        price_ranks = pd.Series(window).rank(method="average").values
        d = np.sum((time_ranks - price_ranks) ** 2)
        out[i] = (1.0 - (6.0 * d) / (period * (period**2 - 1))) * 100.0

    return pd.Series(out, index=close.index, name=f"RCI{period}")


def attach_rci(df: pd.DataFrame, period: int = 9, price_col: str = "close") -> pd.DataFrame:
    """DataFrame に RCI 列を追加する。"""
    col = f"RCI{period}"
    if col not in df.columns:
        df[col] = compute_rci(df[price_col], period=period)
    return df


def jdg_rci_v_reversal(
    df: pd.DataFrame,
    period: int = 9,
    rci_low: float = -80.0,
    turn_min: float = 5.0,
    lookback: int = 5,
    require_below_zero: bool = True,
) -> int:
    """買い向け RCI V字反転。1=シグナル、0=なし。"""
    col = f"RCI{period}"
    if col not in df.columns:
        df = attach_rci(df, period=period)

    tail = df[col].dropna().tail(max(lookback + 2, period + 2))
    if len(tail) < 3:
        return 0

    rci_prev = float(tail.iloc[-2])
    rci_now = float(tail.iloc[-1])
    recent = tail.iloc[:-1].tail(lookback)

    had_bottom = bool((recent <= rci_low).any())
    turned_up = (rci_now - rci_prev) >= turn_min and rci_now > rci_prev
    still_early = (rci_now < 0) if require_below_zero else True

    return 1 if had_bottom and turned_up and still_early else 0


def jdg_rci_turn_down(
    df: pd.DataFrame,
    period: int = 9,
    turn_min: float = 5.0,
    peak_min: float = 20.0,
    lookback: int = 5,
) -> int:
    """買い保有の手仕舞い: RCI が反発後に反転下落。1=決済シグナル、0=継続。"""
    col = f"RCI{period}"
    if col not in df.columns:
        df = attach_rci(df, period=period)

    tail = df[col].dropna().tail(max(lookback + 2, period + 2))
    if len(tail) < 3:
        return 0

    rci_prev = float(tail.iloc[-2])
    rci_now = float(tail.iloc[-1])
    recent_peak = float(tail.iloc[:-1].tail(lookback).max())

    turned_down = (rci_prev - rci_now) >= turn_min and rci_now < rci_prev
    had_bounce = recent_peak >= peak_min

    return 1 if turned_down and had_bounce else 0


def jdg_rci_turn_up(
    df: pd.DataFrame,
    period: int = 9,
    turn_min: float = 5.0,
) -> int:
    """RCI が前日比で上向き。1=上向き、0=それ以外。"""
    col = f"RCI{period}"
    if col not in df.columns:
        df = attach_rci(df, period=period)

    tail = df[col].dropna().tail(3)
    if len(tail) < 2:
        return 0

    rci_prev = float(tail.iloc[-2])
    rci_now = float(tail.iloc[-1])
    turned_up = (rci_now - rci_prev) >= turn_min and rci_now > rci_prev
    return 1 if turned_up else 0
