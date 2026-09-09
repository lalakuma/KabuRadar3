"""バックテスト用の状態モデル."""

from __future__ import annotations

import os
from datetime import date, datetime

import pandas as pd

from kaburadar3.settings import screening as conf
from kaburadar3.settings.runtime import apply_exit_profile_to_judge
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
        as_of_date: date | None = None,
        breadth_block_dates: set[date] | None = None,
    ):
        self.sell_period = sell_period
        self.past_period = past_period
        self.srsi_hi = srsi_hi
        self.srsi_low = srsi_low
        self.ent_rest = ent_rest
        self.as_of_date = as_of_date
        self.breadth_block_dates = breadth_block_dates

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
    rsi_prep = False
    rsi_prep_bars = 0
    rsi60_reached = False
    rsi10_reached = False
    ma5_rally_seen = False


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
        self.jdg_rci_seq = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_RCI_SEQ, default="0"))
        self.rci_prep_max_bars = int(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_PREP_MAX_BARS, default="20")
        )
        self.jdg_rci_exit = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_RCI_EXIT, default="0"))
        self.rci_exit_turn_min = float(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_EXIT_TURN_MIN, default="5")
        )
        self.rci_exit_peak = float(conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_EXIT_PEAK, default="20"))
        self.rci_exit_profit_only = int(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_EXIT_PROFIT_ONLY, default="0")
        )
        self.rci_exit_rsi_min = float(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RCI_EXIT_RSI_MIN, default="0")
        )
        self.rsi60_hold_rci_up = int(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RSI60_HOLD_RCI_UP, default="0")
        )
        self.rsi60_rci_turn_min = float(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RSI60_RCI_TURN_MIN, default="0")
        )
        self.rsi60_rci_peak = float(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RSI60_RCI_PEAK, default="0")
        )
        self.jdg_rsi10_recross_exit = int(
            conf.get_config(scrsec, conf.CONF_KEY_JDG_RSI10_RECROSS_EXIT, default="0")
        )
        self.rsi_recross_exit_level = float(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_RSI_RECROSS_EXIT_LEVEL, default="10")
        )
        self.jdg_stop_loss = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_STOP_LOSS, default="0"))
        self.stop_loss_pct = float(conf.get_config(scrsec, conf.CONF_KEY_SCR_STOP_LOSS_PCT, default="3"))
        self.jdg_ma5_exit = int(conf.get_config(scrsec, conf.CONF_KEY_JDG_MA5_EXIT, default="0"))
        self.ma5_exit_mode = str(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_MA5_EXIT_MODE, default="offset")
        ).strip().lower()
        self.ma5_offset_pct = float(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_MA5_OFFSET_PCT, default="-1.0")
        )
        self.ma5_proximity_pct = float(
            conf.get_config(scrsec, conf.CONF_KEY_SCR_MA5_PROXIMITY_PCT, default="1.5")
        )
        self.ma5_rally_pct = float(conf.get_config(scrsec, conf.CONF_KEY_SCR_MA5_RALLY_PCT, default="1.0"))
        self.ma5_min_bars = int(conf.get_config(scrsec, conf.CONF_KEY_SCR_MA5_MIN_BARS, default="1"))
        self.ma5_profit_only = int(conf.get_config(scrsec, conf.CONF_KEY_SCR_MA5_PROFIT_ONLY, default="1"))
        apply_exit_profile_to_judge(self)
