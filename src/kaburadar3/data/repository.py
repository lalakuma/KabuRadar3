"""SQLite リポジトリ（銘柄・価格・TradeHist）."""

from __future__ import annotations

import sqlite3

import pandas as pd

from kaburadar3.settings import screening as conf


def connect_db():
    dbname = conf.get_config(conf.CONF_SEC_DATABASE, conf.CONF_KEY_PATH_DB)
    conn = sqlite3.connect(dbname, isolation_level=None)
    cursor = conn.cursor()
    return conn, cursor


def close_db(conn) -> None:
    conn.close()


def create_tradehist(conn, cursor) -> None:
    sql = """CREATE TABLE IF NOT EXISTS TradeHist (
            "Index" DATE,
            "code" INTEGER,
            "open" INTEGER,
            "close" INTEGER,
            "PF" REAL,
            "mark" TEXT,
            "buygain" INTEGER,
            "sellgain" INTEGER,
            "latent" INTEGER,
            "income" INTEGER,
            "name" TEXT,
            "sangyou" TEXT
        ); """
    cursor.execute(sql)
    conn.commit()


def read_rec_period(conn, cursor, code, start, end):
    sql = f'SELECT * FROM tbl_{code} WHERE datetime BETWEEN "{start}" AND "{end}"'
    return pd.read_sql(sql, conn)


def read_rec_all(conn, cursor, tbl):
    sql = f"SELECT * FROM {tbl}"
    return pd.read_sql(sql, conn)


def read_code_record(conn, cursor, code):
    sql = f'SELECT * FROM tbl_codelist WHERE Code = "{code}"'
    cursor.execute(sql)
    for cd in cursor.fetchall():
        return cd[1], cd[3]
    return "", ""


def read_code_all(cursor, tbl):
    sql = f'SELECT * FROM "{tbl}"'
    cursor.execute(sql)
    return [cd[0] for cd in cursor.fetchall()]


def insert_data_from_df_to_db(conn, df) -> None:
    df.to_sql("TradeHist", conn, if_exists="append", index=False)


def delete_all_records(conn, table_name) -> None:
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table_name}")
        conn.commit()
    except sqlite3.OperationalError as e:
        print(e)


def delete_tbl(conn, tbl) -> None:
    sql = f"DROP TABLE if exists {tbl}"
    conn.execute(sql)
    conn.commit()
