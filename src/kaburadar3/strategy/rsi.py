"""短期 RSI インジケータとシグナル判定."""

from __future__ import annotations

import numpy as np
import pandas as pd

from kaburadar3.domain import constants as DEF


def rsi_tradingview(ohlc: pd.DataFrame, period: int = 14, round_rsi: bool = False):
    delta = ohlc["close"].diff()
    up = delta.copy()
    up[up < 0] = 0
    up = pd.Series.ewm(up, alpha=1 / period).mean()
    down = delta.copy()
    down[down > 0] = 0
    down *= -1
    down = pd.Series.ewm(down, alpha=1 / period).mean()
    rsi = np.where(up == 0, 0, np.where(down == 0, 100, 100 - (100 / (1 + up / down))))
    if period == 14:
        ohlc["RSI"] = np.round(rsi, 2) if round_rsi else rsi
    elif period == 4:
        ohlc["RSI4"] = np.round(rsi, 2) if round_rsi else rsi
    return ohlc


def jdg_rsi_short(sb_mode, df, srsi_low, jdg_rsi4rev):
    sigsw_rsi = 0
    taildf = df.tail(5)
    rsi4 = taildf["RSI4"].values[-1]
    rsi4_pre1 = taildf["RSI4"].values[-2]

    if sb_mode == DEF.MODE_BUY:
        if jdg_rsi4rev == 0:
            if rsi4 < srsi_low:
                sigsw_rsi = 1
        else:
            if rsi4_pre1 < srsi_low and rsi4_pre1 < rsi4 and rsi4 < 40:
                sigsw_rsi = 1
    elif sb_mode == DEF.MODE_SELL:
        if jdg_rsi4rev == 0:
            if rsi4 > (100 - srsi_low):
                sigsw_rsi = 1
        else:
            if rsi4_pre1 > (100 - srsi_low) and rsi4_pre1 > rsi4 and rsi4 > (100 - 40):
                sigsw_rsi = 1
    return sigsw_rsi


def jdg_rsi_shortkessai(sb_mode, df, srsi_hi, srsi_low):
    sigsw_rsi = False
    taildf = df.tail(5)
    rsi4 = taildf["RSI4"].values[-1]

    if sb_mode == DEF.MODE_BUY:
        if srsi_hi < rsi4:
            sigsw_rsi = True
    elif sb_mode == DEF.MODE_SELL:
        if (100 - srsi_hi) > rsi4:
            sigsw_rsi = True
    return sigsw_rsi
