"""短期 RSI (SCR_JDG_RSI4) 専用バックテストエンジン."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy
import pandas as pd

from kaburadar3.data import repository as db
from kaburadar3.domain import constants as DEF
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import rsi as tc_rsi
from kaburadar3.strategy import rci as tc_rci
from kaburadar3.strategy.models import CodePrice, Judge, KabInf, TradeInfo

_DATE_SENTINEL = object()

lst_codes: list[str] = []


def backtst_proc(code, df_indicator, Prm, conn=None, cursor=None):
    global lst_codes
    lst_codes = []
    if conn is None or cursor is None:
        conn, cursor = db.connect_db()
    scrsec = conf.CONF_SEC_SCR
    cp = CodePrice()
    ti = TradeInfo()
    jg = Judge(scrsec)

    cp.code = code
    ret = 0
    cnt_buyholddays = 0
    cp.plusgain = 0.0
    cp.minusgain = 0.0
    ti.isreserved = False
    idx_date = _DATE_SENTINEL
    iBuyRestCount = 0
    req_sb_mode = int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SELLBUY))
    ent_timing = int(conf.get_config(scrsec, conf.CONF_KEY_SCR_ENT_TIMING))

    if req_sb_mode != DEF.MODE_BOTH:
        ti.sb_mode = req_sb_mode

    today = date.today()
    str_date_sta = datetime.strftime(today + timedelta(days=Prm.past_period), "%Y-%m-%d")
    str_date_end = datetime.strftime(today + timedelta(days=1), "%Y-%m-%d")

    df = db.read_rec_period(conn, cursor, str(cp.code), str_date_sta, str_date_end)
    try:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"])
        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df[numeric_cols] = df[numeric_cols].fillna(0)
        for col in numeric_cols:
            df[col] = df[col].astype("int64")
        df["SMA5"] = df["close"].rolling(window=5).mean()
        df["SMA25"] = df["close"].rolling(window=25).mean()
    except Exception as e:
        print(f"Error details: {e}")
        print(str(cp.code) + ": Error")
        return -1

    if len(df) == 0:
        return -1
    price = df["close"].values[-1]
    if price > 4000:
        print("price over :" + str(price))
        return -1

    df_price = df.set_index("datetime").loc[:, ["open", "high", "low", "close", "volume", "SMA5", "SMA25"]]
    df_price["mark"] = ""
    df_price["buy"] = 0
    df_price["buygain"] = 0
    df_price["sell"] = 0
    df_price["sellgain"] = 0
    df_price["income"] = 0
    df_price["RSI"] = 0
    df_price = tc_rsi.rsi_tradingview(df_price, 4)
    df_price = tc_rci.attach_rci(df_price, period=jg.rci_period)

    bkdf = pd.DataFrame()
    for row in df_price.itertuples():
        if row.close > 6000 and ti.buy_pos == 0:
            return -1

        wkdf = pd.DataFrame([row])
        bkdf = pd.concat([bkdf, wkdf], ignore_index=True)
        lastidx_bk = len(bkdf) - 1
        if numpy.isnan(wkdf["SMA25"].values).any():
            continue

        if iBuyRestCount > 0:
            iBuyRestCount -= 1

        if idx_date is _DATE_SENTINEL:
            idx_predate = row[0]
        else:
            idx_predate = idx_date
        idx_date = row[0]

        i_close_pre1 = cp.i_close
        cp.i_open = row.open
        cp.i_close = row.close
        cp.i_low = row.low
        cp.i_high = row.high
        cp.i_sma5 = row.SMA5
        cp.i_presma25 = cp.i_sma25
        cp.i_sma25 = row.SMA25

        if req_sb_mode == DEF.MODE_BOTH:
            if cp.i_sma25 > cp.i_close:
                ti.sb_mode = DEF.MODE_BUY
            else:
                ti.sb_mode = DEF.MODE_SELL

        cnt_buyholddays, iBuyRestCount = kessai_proc(
            cp, ti, jg, bkdf, Prm, row, idx_date, lastidx_bk, cnt_buyholddays, iBuyRestCount
        )

        if ti.buy_pos == 0 and ti.sell_pos == 0 and iBuyRestCount == 0:
            if ti.isreserved is False:
                if judge_signal(cp, ti, jg, bkdf, Prm) is False:
                    continue
            else:
                if jg.jdg_rsvent:
                    if ti.sb_mode == DEF.MODE_BUY and i_close_pre1 >= cp.i_open:
                        ti.isreserved = False
                        continue
                    if ti.sb_mode == DEF.MODE_SELL and i_close_pre1 <= cp.i_open:
                        ti.isreserved = False
                        continue
            entry_proc(cp, ti, lst_codes, bkdf, lastidx_bk, idx_date, ent_timing)

        if Prm.sell_period == 0:
            cnt_buyholddays, iBuyRestCount = kessai_proc(
                cp, ti, jg, bkdf, Prm, row, idx_date, lastidx_bk, cnt_buyholddays, iBuyRestCount
            )

    Prm.lst_result = lst_codes
    Prm.outdf = bkdf
    Prm.win = ti.win
    Prm.lose = ti.lose
    Prm.income = ti.income
    Prm.entrycnt = ti.entrycnt
    Prm.outcodecsv = ti.outcodecsv
    Prm.plusgain = int(round(cp.plusgain, 1) * 100)
    Prm.minusgain = int(round(cp.minusgain, 1) * 100)
    if ti.win != 0 or ti.lose != 0:
        Prm.winrate = (ti.win / (ti.win + ti.lose)) * 100
    else:
        Prm.winrate = 0

    if cp.plusgain != 0 and cp.minusgain != 0:
        wkpf = cp.plusgain / abs(cp.minusgain)
    else:
        wkpf = cp.plusgain if cp.minusgain == 0 else 0
    Prm.pf = "{:.1f}".format(wkpf)

    return ret, lst_codes


def kessai_proc(cp, ti, jg, bkdf, Prm, row, idx_date, lastidx_bk, cnt_buyholddays, RestCount):
    sellgain = 0
    if ti.sell_pos > 0:
        cnt_buyholddays += 1
        bkdf.loc[lastidx_bk, "mark"] = "継続"
        if tc_rsi.jdg_rsi_shortkessai(ti.sb_mode, bkdf, Prm.srsi_hi, Prm.srsi_low):
            ti.kessai_sell = True
            sell_kessai_val = cp.i_close
        elif Prm.sell_period == -1:
            ti.kessai_sell = True
            sell_kessai_val = cp.i_open
        elif cnt_buyholddays >= Prm.sell_period:
            ti.kessai_sell = True
            sell_kessai_val = cp.i_close
        else:
            print(cp.code, ":", str(idx_date.date()), "継続")

        if ti.kessai_sell:
            diff = ti.sell_price - sell_kessai_val
            sellgain = diff * 100
            ti.income += sellgain
            ti.kessai_sell = False
            ti.sell_pos = 0
            ti.sell_price = 0
            print(cp.code, ":", str(idx_date.date()), "返買", str(diff))
            if sellgain > 0:
                ti.win += 1
                cp.plusgain += (diff / cp.i_close) * 1000
            elif sellgain < 0:
                ti.lose += 1
                cp.minusgain += (diff / cp.i_close) * 1000
            bkdf.loc[lastidx_bk, "mark"] = "返買"
            RestCount = Prm.ent_rest

    buygain = 0
    if ti.buy_pos > 0:
        cnt_buyholddays += 1
        bkdf.loc[lastidx_bk, "mark"] = "継続"
        if tc_rsi.jdg_rsi_shortkessai(ti.sb_mode, bkdf, Prm.srsi_hi, Prm.srsi_low):
            ti.kessai_buy = True
            buy_kessai_val = cp.i_close
        elif Prm.sell_period == -1:
            ti.kessai_buy = True
            buy_kessai_val = cp.i_open
        elif cnt_buyholddays >= Prm.sell_period:
            ti.kessai_buy = True
            buy_kessai_val = cp.i_close

        if ti.kessai_buy:
            diff = buy_kessai_val - ti.buy_price
            buygain = diff * 100
            ti.income += buygain
            ti.kessai_buy = False
            ti.buy_pos = 0
            ti.buy_price = 0
            cnt_buyholddays = 0
            print(cp.code, ":", str(idx_date.date()), "返売", str(diff))
            if buygain > 0:
                ti.win += 1
                cp.plusgain += (diff / cp.i_close) * 1000
            elif buygain < 0:
                ti.lose += 1
                cp.minusgain += (diff / cp.i_close) * 1000
            bkdf.loc[lastidx_bk, "mark"] = "返売"
            RestCount = Prm.ent_rest

    bkdf.loc[lastidx_bk, "buy"] = ti.buy_pos
    bkdf.loc[lastidx_bk, "buygain"] = buygain
    bkdf.loc[lastidx_bk, "sell"] = ti.sell_pos
    bkdf.loc[lastidx_bk, "sellgain"] = sellgain
    bkdf.loc[lastidx_bk, "income"] = ti.income
    return cnt_buyholddays, RestCount


def judge_signal(cp, ti, jg, bkdf, Prm) -> bool:
    if jg.jdg_rsi4 and tc_rsi.jdg_rsi_short(ti.sb_mode, bkdf, Prm.srsi_low, jg.jdg_rsi4rev) == 0:
        return False
    if ti.sb_mode == DEF.MODE_BUY and jg.jdg_rci:
        if (
            tc_rci.jdg_rci_v_reversal(
                bkdf,
                period=jg.rci_period,
                rci_low=jg.rci_low,
                turn_min=jg.rci_turn_min,
                lookback=jg.rci_lookback,
            )
            == 0
        ):
            return False
    return True


def entry_proc(cp, ti, lst_codes, bkdf, lastidx_bk, idx_date, ent_timing):
    ti.outcodecsv = True
    if ti.sb_mode == DEF.MODE_BUY:
        if ent_timing == 1 and ti.isreserved is False:
            strtrd = "買シ"
            ti.isreserved = True
        else:
            strtrd = "新買"
            ti.isreserved = False
            ti.buy_pos += 1
            ti.entrycnt += 1
            bkdf.loc[lastidx_bk, "buy"] = ti.buy_pos
            if ti.buy_price == 0:
                ti.buy_price = cp.i_close if ent_timing == 0 else cp.i_open
        bkdf.loc[lastidx_bk, "mark"] = strtrd
        add_entry_list(cp, lst_codes, idx_date, strtrd, ti.buy_price)
    else:
        if ent_timing == 1 and ti.isreserved is False:
            strtrd = "売シ"
            ti.isreserved = True
        else:
            ti.isreserved = False
            ti.sell_pos += 1
            ti.entrycnt += 1
            bkdf.loc[lastidx_bk, "sell"] = ti.sell_pos
            strtrd = "新売"
            if ti.sell_price == 0:
                ti.sell_price = cp.i_close if ent_timing == 0 else cp.i_open
        bkdf.loc[lastidx_bk, "mark"] = strtrd
        add_entry_list(cp, lst_codes, idx_date, strtrd, ti.sell_price)


def add_entry_list(cp, lst_codes, idx_date, strtrd, trdval):
    print(cp.code, ":", str(idx_date.date()), strtrd)
    str_fmt = "¥{:,d}".format(trdval)
    lst_codes.append(str(cp.code) + ":" + str(idx_date.date()) + " " + str_fmt)
