"""yfinance による株価テーブル更新."""

from __future__ import annotations

import argparse
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yfinance as yf

from kaburadar3.settings.loader import read_config
from kaburadar3.settings.paths import PROJECT_ROOT


@dataclass(frozen=True)
class FetchSpec:
    label: str
    ptype: str  # "day" or "year"
    period: int


MENU_SPECS = {
    "1": FetchSpec("1日", "day", 1),
    "2": FetchSpec("10日", "day", 10),
    "3": FetchSpec("30日", "day", 30),
    "4": FetchSpec("100日", "day", 100),
    "5": FetchSpec("5年", "year", 5),
    "6": FetchSpec("5日", "day", 5),
}


def _resolve_db_path() -> Path:
    raw = read_config("DATABASE", "PATH_DB")
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (PROJECT_ROOT / candidate).resolve()


def _ticker_code(code: str) -> str:
    if code == "0":
        return "^N225"
    if code == "800":
        return "^DJI"
    return f"{code}.T"


def _fetch_price_data(code: str, spec: FetchSpec) -> pd.DataFrame:
    period_str = f"{spec.period}{'d' if spec.ptype == 'day' else 'y'}"
    ticker = yf.Ticker(_ticker_code(code))
    df = ticker.history(period=period_str, interval="1d", auto_adjust=False)
    if df.empty:
        return pd.DataFrame()

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df = df[["open", "high", "low", "close", "volume"]]
    df.index.name = "datetime"
    return df


def _read_codes(cursor: sqlite3.Cursor) -> list[str]:
    cursor.execute('SELECT * FROM "tbl_codelist"')
    return [row[0] for row in cursor.fetchall()]


def _read_table_names(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
    return {row[0] for row in cursor.fetchall()}


def _delete_after_date(cursor: sqlite3.Cursor, code: str, date_str: str) -> None:
    cursor.execute(f'DELETE FROM "tbl_{code}" WHERE datetime >= ?', (date_str,))


def _pick_spec_with_menu() -> FetchSpec:
    print("株価更新期間を選んでください:")
    for key, spec in MENU_SPECS.items():
        print(f"  {key}. {spec.label}")

    while True:
        choice = input("番号を入力してください [1-6]: ").strip()
        if choice in MENU_SPECS:
            return MENU_SPECS[choice]
        print("入力エラー: 1〜6 の番号を指定してください。")


def _pick_spec_from_args(choice: str | None) -> FetchSpec:
    if choice and choice in MENU_SPECS:
        return MENU_SPECS[choice]
    return _pick_spec_with_menu()


def run(spec: FetchSpec, sleep_sec: float = 0.1) -> int:
    db_path = _resolve_db_path()
    if not db_path.exists():
        print(f"DBが見つかりません: {db_path}")
        return 1

    conn = sqlite3.connect(db_path, isolation_level=None)
    cursor = conn.cursor()
    try:
        codes = _read_codes(cursor)
        tables = _read_table_names(cursor)
        print(f"読み込んだ銘柄数: {len(codes)} / 更新期間: {spec.label}")

        for idx, code in enumerate(codes, start=1):
            table_name = f"tbl_{code}"
            if table_name not in tables:
                print(f"[{idx}/{len(codes)}] {code}: tableなしのためスキップ")
                continue

            try:
                df = _fetch_price_data(code, spec)
            except Exception as exc:  # noqa: BLE001
                print(f"[{idx}/{len(codes)}] {code}: 取得エラー {exc}")
                continue

            if df.empty:
                print(f"[{idx}/{len(codes)}] {code}: データなし")
                continue

            first_dt = str(df.index[0])
            _delete_after_date(cursor, code, first_dt)
            df.to_sql(table_name, conn, if_exists="append")
            print(f"[{idx}/{len(codes)}] {code}: {len(df)}件 更新")
            time.sleep(sleep_sec)
    finally:
        conn.close()

    print("update_prices: completed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="株価更新（期間選択メニュー付き）")
    parser.add_argument(
        "--menu",
        choices=list(MENU_SPECS.keys()),
        help="期間を番号指定で直接実行 (1=1日,2=10日,3=30日,4=100日,5=5年,6=5日)",
    )
    args = parser.parse_args()
    spec = _pick_spec_from_args(args.menu)
    return run(spec)
