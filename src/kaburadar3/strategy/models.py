"""バックテスト用の状態モデル."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd

from kaburadar3.settings import screening as conf
from kaburadar3.settings.encoding import CSV_ENCODING


class KabInf:
    lst_result: list = []
    outdf = pd.DataFrame()
    winrate = 0
    adopt_rsi = 0
    pf = 0
    entrycnt = 0
    outcodecsv = False
    win = 0
    lose = 0
    income = 0
    plusgain = 0
    minusgain = 0

    def __init__(
        self,
        sell_period: int = 3,
        past_period: int = -1200,
        srsi_hi: int = 70,
        srsi_low: int = 30,
        ent_rest: int = 0,
    ):
        self.sell_period = sell_period
        self.past_period = past_period
        self.srsi_hi = srsi_hi
        self.srsi_low = srsi_low
        self.ent_rest = ent_rest

    def get_winrate(self) -> int:
        if self.win == 0 and self.lose == 0:
            self.winrate = 0
        else:
            self.winrate = int((self.win / (self.win + self.lose)) * 100)
        return self.winrate

    def write_prm_tocsv(self, analys_path: str) -> None:
        tup_prm = {
            "sell_period": self.sell_period,
            "past_period": self.past_period,
            "srsi_hi": self.srsi_hi,
            "srsi_low": self.srsi_low,
        }
        strdt = datetime.strftime(datetime.now(), "%Y-%m-%d_%H%M%S")
        df_prm = pd.DataFrame(
            tup_prm,
            index=[datetime.strftime(datetime.now(), "%Y/%m/%d %H:%M:%S")],
        )
        if not os.path.exists(analys_path):
            os.mkdir(analys_path)
        df_prm.to_csv(analys_path + "設定_" + strdt + ".csv", encoding=CSV_ENCODING)


class CodePrice:
    code = 0
    i_open = 0
    i_close = 0
    i_low = 0
    i_high = 0
    i_sma5 = 0
    i_sma25 = 0
    i_presma25 = 0
    plusgain = 0.0
    minusgain = 0.0


class TradeInfo:
    sb_mode = 0
    buy_price = 0
    buy_pos = 0
    sell_price = 0
    sell_pos = 0
    kessai_buy = False
    kessai_sell = False
    isreserved = False
    entrycnt = 0
    win = 0
    lose = 0
    plusgain = 0
    minusgain = 0
    income = 0
    outcodecsv = False


class Judge:
    def __init__(self, scrsec: str) -> None:
        self.jdg_rsi4 = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_RSI4))
        self.jdg_rsi4rev = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_RSI4REV))
        self.jdg_rsvent = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_RSVENT))
        self.jdg_rci = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_RCI, default="0"))
        self.rci_period = int(conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_PERIOD, default="9"))
        self.rci_low = float(conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_LOW, default="-80"))
        self.rci_turn_min = float(conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_TURN_MIN, default="5"))
        self.rci_lookback = int(conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_LOOKBACK, default="5"))
