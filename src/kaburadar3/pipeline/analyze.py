"""全銘柄バックテスト解析パイプライン."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from kaburadar3.data import repository as db
from kaburadar3.pipeline import aggregate as shuukei
from kaburadar3.settings import screening as conf
from kaburadar3.settings.loader import copy_config_snapshot
from kaburadar3.settings.encoding import CSV_ENCODING
from kaburadar3.settings.paths import LOG_DIR
from kaburadar3.strategy import engine as bktst
from kaburadar3.strategy.models import KabInf

STANCE = "LO"

# 終了コード: 0=成功, 1=有効銘柄はあるが1件も出力なし, 2=集計CSV未生成
EXIT_OK = 0
EXIT_NO_OUTPUT = 1
EXIT_NO_SUMMARY = 2


@dataclass
class AnalyzeStats:
    enabled: int = 0
    skipped: int = 0
    written: int = 0


def backtest_failed(result) -> bool:
    """backtst_proc の失敗（-1）を判定する。"""
    return result == -1


def compute_exit_code(stats: AnalyzeStats, summary_csv: Path | None) -> int:
    if stats.enabled == 0:
        return EXIT_OK
    if stats.written == 0:
        return EXIT_NO_OUTPUT
    if summary_csv is None or not summary_csv.is_file():
        return EXIT_NO_SUMMARY
    return EXIT_OK


def _setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("kaburadar.pipeline.analyze")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    fh = logging.FileHandler(LOG_DIR / "debug.log", encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


def _write_csv(dt: KabInf, kekka_path: str, code: str, coderec) -> None:
    if not dt.outcodecsv:
        return
    winrate = KabInf.get_winrate(dt)
    wlstr = (
        "_rsi"
        + str(dt.adopt_rsi)
        + "_W"
        + str(dt.win)
        + "L"
        + str(dt.lose)
        + "_"
        + str(winrate)
        + "%_YEN"
        + str(dt.income)
        + "_PF"
        + str(dt.pf)
        + "_pg"
        + str(dt.plusgain)
        + "_mg"
        + str(dt.minusgain)
        + "_"
        + coderec[0].replace("\uff0d", "-")
        + "_"
        + coderec[1].replace("\uff0d", "-")
        + "_"
    )
    out_path = os.path.join(kekka_path, f"code{code}{wlstr}.csv")
    dt.outdf.to_csv(out_path, encoding=CSV_ENCODING)


STANCE = "LO"  # run() 内で上書き


def _prepare_output_dir(kekka_path: str, stance: str) -> None:
    path = Path(kekka_path)
    path.mkdir(parents=True, exist_ok=True)
    for csv_file in path.glob("*.csv"):
        csv_file.unlink()
    summary = path / f"集計_{stance}.xlsx"
    if summary.exists():
        summary.unlink()


def _build_kab_inf(scrsec: str, past_period: int) -> KabInf:
    return KabInf(
        sell_period=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SELL_PERIOD)),
        past_period=past_period,
        srsi_hi=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_HI)),
        srsi_low=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_SRSI_LOW)),
        ent_rest=int(conf.get_config(scrsec, conf.CONF_KEY_SCR_ENTRY_REST)),
    )


def _find_summary_csv(results_dir: Path) -> Path | None:
    candidates = sorted(results_dir.glob("Y*_PF*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def run() -> int:
    logger = _setup_logger()
    config_path = conf.resolve_config_path()
    stance = conf.config_stance(config_path)
    logger.info("解析を開始します (%s / 短期RSI)。", config_path.name)

    stats = AnalyzeStats()
    kekka_path = ""
    conn, cursor = db.connect_db()
    try:
        codes = db.read_code_all(cursor, "tbl_codelist")
        scrsec = conf.CONF_SEC_SCR
        past_period = int(conf.get_config(scrsec, conf.CONF_KEY_SCR_PAST_PERIOD)) * (-1)

        cls_dt = _build_kab_inf(scrsec, past_period)
        kekka_path = conf.get_config(conf.CONF_SEC_SHUUKEI, conf.CONF_KEY_PATH_HONBAN)

        _prepare_output_dir(kekka_path, stance)
        cls_dt.write_prm_tocsv(kekka_path)
        copy_config_snapshot(Path(kekka_path), config_path=config_path)

        df_indicator = pd.DataFrame()
        df_set = db.read_rec_all(conn, cursor, "tbl_code_set")
        df_set = df_set.set_index("code")

        for code in codes:
            print("CODE=", code)
            if str(code) not in df_set.index or df_set.at[str(code), "Enable"] == 0:
                continue

            stats.enabled += 1
            cls_dt.outcodecsv = False
            result = bktst.backtst_proc(code, df_indicator, cls_dt, conn, cursor)
            if backtest_failed(result):
                stats.skipped += 1
                logger.debug("skip code=%s (backtest failed)", code)
                continue

            coderec = db.read_code_record(conn, cursor, code)
            _write_csv(cls_dt, kekka_path, str(code), coderec)
            if cls_dt.outcodecsv:
                stats.written += 1

        fullpath_shuukei = shuukei.shuukei_toCsv(kekka_path)
        _shuukei, _filepath, final_rieki = shuukei.shuukei_makeExl(kekka_path, stance)

        if fullpath_shuukei:
            newfilename = fullpath_shuukei.replace("PF", f"Y{final_rieki}_PF")
            os.rename(fullpath_shuukei, newfilename)

        summary_csv = _find_summary_csv(Path(kekka_path))
        exit_code = compute_exit_code(stats, summary_csv)

        summary = (
            f"enabled={stats.enabled} written={stats.written} skipped={stats.skipped}"
        )
        if exit_code == EXIT_OK:
            logger.info("解析を完了しました (%s).", summary)
            print(f"解析完了: {summary}")
        elif exit_code == EXIT_NO_OUTPUT:
            logger.error("解析失敗: 有効銘柄のうち出力 0 件 (%s).", summary)
            print(f"解析失敗 (exit={exit_code}): {summary}")
        else:
            logger.error("解析失敗: 集計 CSV がありません (%s).", summary)
            print(f"解析失敗 (exit={exit_code}): {summary}")
        return exit_code
    finally:
        db.close_db(conn)
