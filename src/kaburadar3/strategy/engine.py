"""短期 RSI (SCR_JDG_RSI4) 専用バックテストエンジン."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy
import pandas as pd

from kaburadar3.data import repository as db
from kaburadar3.domain import constants as DEF
from kaburadar3.settings import screening as conf
from kaburadar3.strategy import ma5 as tc_ma5
from kaburadar3.strategy.ma5 import MA5_MODE_BAND, MA5_MODE_OFFSET, MA5_MODE_PULLBACK
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

    anchor = Prm.as_of_date if Prm.as_of_date is not None else date.today()
    str_date_sta = datetime.strftime(anchor + timedelta(days=Prm.past_period), "%Y-%m-%d")
    str_date_end = datetime.strftime(anchor + timedelta(days=1), "%Y-%m-%d")

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
        # 決済は前日確定の5日線を使う（当日終値込みのSMA5はルックアヘッドになる）
        df["SMA5_PREV"] = df["SMA5"].shift(1)
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

    df_price = df.set_index("datetime").loc[
        :, ["open", "high", "low", "close", "volume", "SMA5", "SMA5_PREV", "SMA25"]
    ]
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
        cp.i_sma5_prev = row.SMA5_PREV
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
            if jg.jdg_rci_seq:
                _update_rsi_prep(ti, jg, bkdf, Prm)
            if ti.isreserved is False:
                if judge_signal(cp, ti, jg, bkdf, Prm, idx_date) is False:
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


def _current_rsi4(bkdf) -> float:
    if "RSI4" not in bkdf.columns or not bkdf["RSI4"].notna().any():
        return 0.0
    return float(bkdf["RSI4"].dropna().iloc[-1])


def _rci_params_after_rsi60(jg: Judge, ti: TradeInfo) -> tuple[float, float, float]:
    """RSI60到達後は感度を上げたRCIパラメータを返す。未設定なら通常値。"""
    if ti.rsi60_reached and jg.rsi60_rci_turn_min > 0:
        turn_min = jg.rsi60_rci_turn_min
        peak_min = jg.rsi60_rci_peak if jg.rsi60_rci_peak > 0 else jg.rci_exit_peak
    else:
        turn_min = jg.rci_exit_turn_min
        peak_min = jg.rci_exit_peak
    return turn_min, peak_min, jg.rci_turn_min


def _rci_turn_up_min(jg: Judge, ti: TradeInfo, *, rsi_hit: bool) -> float:
    """RSI60超え後は上向き判定も感度を上げる。"""
    if (ti.rsi60_reached or rsi_hit) and jg.rsi60_rci_turn_min > 0:
        return jg.rsi60_rci_turn_min
    return jg.rci_turn_min


def _ma5_ref(cp) -> float:
    """決済判定に使う5日線（前日終値までで確定した値）."""
    ref = cp.i_sma5_prev
    if ref is None or (isinstance(ref, float) and numpy.isnan(ref)):
        return 0.0
    return float(ref)


def _ma5_exit_hit(cp, ti, jg, cnt_buyholddays: int) -> bool:
    if not jg.jdg_ma5_exit or ti.sb_mode != DEF.MODE_BUY or cnt_buyholddays < jg.ma5_min_bars:
        return False
    sma5 = _ma5_ref(cp)
    if sma5 <= 0:
        return False
    mode = jg.ma5_exit_mode
    if mode == MA5_MODE_OFFSET:
        return tc_ma5.high_reached_ma5_offset(cp.i_high, sma5, jg.ma5_offset_pct)
    if mode == MA5_MODE_BAND:
        return tc_ma5.high_near_ma5(cp.i_high, sma5, jg.ma5_proximity_pct)
    if mode == MA5_MODE_PULLBACK:
        return ti.ma5_rally_seen and tc_ma5.near_ma5(
            cp.i_close, cp.i_low, sma5, jg.ma5_proximity_pct
        )
    return tc_ma5.high_reached_ma5_offset(cp.i_high, sma5, jg.ma5_offset_pct)


def _buy_exit_signal(cp, ti, jg, bkdf, Prm, cnt_buyholddays) -> tuple[bool, int]:
    """買いポジションの決済判定。(決済するか, 決済価格)"""
    if jg.jdg_stop_loss and ti.buy_price > 0:
        pct = (cp.i_close - ti.buy_price) / ti.buy_price * 100.0
        if pct <= -jg.stop_loss_pct:
            return True, cp.i_close
    if _ma5_exit_hit(cp, ti, jg, cnt_buyholddays):
        in_profit = ti.buy_price > 0 and cp.i_close > ti.buy_price
        if not jg.ma5_profit_only or in_profit:
            return True, cp.i_close
    rsi_hit = tc_rsi.jdg_rsi_shortkessai(ti.sb_mode, bkdf, Prm.srsi_hi, Prm.srsi_low)
    turn_up_min = _rci_turn_up_min(jg, ti, rsi_hit=rsi_hit)
    if rsi_hit:
        hold = (
            jg.rsi60_hold_rci_up
            and ti.sb_mode == DEF.MODE_BUY
            and tc_rci.jdg_rci_turn_up(bkdf, period=jg.rci_period, turn_min=turn_up_min) == 1
        )
        if not hold:
            return True, cp.i_close
    turn_min, peak_min, _ = _rci_params_after_rsi60(jg, ti)
    if (
        jg.rsi60_hold_rci_up
        and ti.rsi60_reached
        and ti.sb_mode == DEF.MODE_BUY
        and tc_rci.jdg_rci_turn_down(
            bkdf,
            period=jg.rci_period,
            turn_min=turn_min,
            peak_min=peak_min,
            lookback=jg.rci_lookback,
        )
        == 1
    ):
        return True, cp.i_close
    if jg.jdg_rci_exit and ti.sb_mode == DEF.MODE_BUY:
        if (
            tc_rci.jdg_rci_turn_down(
                bkdf,
                period=jg.rci_period,
                turn_min=jg.rci_exit_turn_min,
                peak_min=jg.rci_exit_peak,
                lookback=jg.rci_lookback,
            )
            == 1
        ):
            in_profit = ti.buy_price > 0 and cp.i_close > ti.buy_price
            rsi4 = float(bkdf["RSI4"].dropna().iloc[-1]) if "RSI4" in bkdf.columns and bkdf["RSI4"].notna().any() else 0.0
            rsi_ok = jg.rci_exit_rsi_min <= 0 or rsi4 >= jg.rci_exit_rsi_min
            if rsi_ok and (not jg.rci_exit_profit_only or in_profit):
                return True, cp.i_close
    if (
        jg.jdg_rsi10_recross_exit
        and ti.rsi10_reached
        and ti.sb_mode == DEF.MODE_BUY
        and _current_rsi4(bkdf) < jg.rsi_recross_exit_level
    ):
        return True, cp.i_close
    if Prm.sell_period == -1:
        return True, cp.i_open
    if cnt_buyholddays >= Prm.sell_period:
        return True, cp.i_close
    return False, cp.i_close


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
        if jg.ma5_exit_mode == MA5_MODE_PULLBACK and tc_ma5.rally_above_ma5(
            cp.i_close, _ma5_ref(cp), jg.ma5_rally_pct
        ):
            ti.ma5_rally_seen = True
        if jg.rsi60_hold_rci_up and tc_rsi.jdg_rsi_shortkessai(
            ti.sb_mode, bkdf, Prm.srsi_hi, Prm.srsi_low
        ):
            ti.rsi60_reached = True
        if _current_rsi4(bkdf) > jg.rsi_recross_exit_level:
            ti.rsi10_reached = True
        exit_now, buy_kessai_val = _buy_exit_signal(cp, ti, jg, bkdf, Prm, cnt_buyholddays)
        if exit_now:
            ti.kessai_buy = True
        else:
            print(cp.code, ":", str(idx_date.date()), "継続")

        if ti.kessai_buy:
            diff = buy_kessai_val - ti.buy_price
            buygain = diff * 100
            ti.income += buygain
            ti.kessai_buy = False
            ti.buy_pos = 0
            ti.buy_price = 0
            ti.rsi60_reached = False
            ti.rsi10_reached = False
            ti.ma5_rally_seen = False
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


def _update_rsi_prep(ti, jg, bkdf, Prm) -> None:
    """RSI 売られすぎで準備フラグ ON。OFF はタイムアウト（SCR_RCI_PREP_MAX_BARS）のみ。"""
    if not jg.jdg_rsi4:
        return
    rsi_signal = tc_rsi.jdg_rsi_short(ti.sb_mode, bkdf, Prm.srsi_low, jg.jdg_rsi4rev) == 1
    if rsi_signal:
        ti.rsi_prep = True
        ti.rsi_prep_bars = 0
        return
    if not ti.rsi_prep:
        return
    ti.rsi_prep_bars += 1
    if jg.rci_prep_max_bars > 0 and ti.rsi_prep_bars > jg.rci_prep_max_bars:
        ti.rsi_prep = False
        ti.rsi_prep_bars = 0


def judge_signal(cp, ti, jg, bkdf, Prm, idx_date) -> bool:
    # 順序型 RSI+RCI: 準備フラグ ON かつ RCI 上向きでエントリー
    if ti.sb_mode == DEF.MODE_BUY and jg.jdg_rci and jg.jdg_rci_seq:
        if Prm.breadth_block_dates:
            trade_day = idx_date.date() if hasattr(idx_date, "date") else idx_date
            if trade_day in Prm.breadth_block_dates:
                return False
        if not ti.rsi_prep:
            return False
        if (
            tc_rci.jdg_rci_turn_up(
                bkdf,
                period=jg.rci_period,
                turn_min=jg.rci_turn_min,
            )
            == 0
        ):
            return False
        ti.rsi_prep = False
        ti.rsi_prep_bars = 0
        return True

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
            ti.rsi60_reached = False
            scr = conf.CONF_SEC_SCR
            jdg_rsi10 = int(conf.get_config(scr, conf.CONF_KEY_JDG_RSI10_RECROSS_EXIT, default="0"))
            recross_level = float(
                conf.get_config(scr, conf.CONF_KEY_SCR_RSI_RECROSS_EXIT_LEVEL, default="10")
            )
            ti.rsi10_reached = jdg_rsi10 == 1 and _current_rsi4(bkdf) > recross_level
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
