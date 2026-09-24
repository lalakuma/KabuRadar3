"""yfinance による株価テーブル更新."""

from __future__ import annotations

import argparse
import sqlite3
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from kaburadar3.settings.loader import read_config
from kaburadar3.settings.paths import PROJECT_ROOT

# 自動選択時に遡って欠損を見る暦日数（約1か月）
AUTO_LOOKBACK_CALENDAR_DAYS = 31
# 参照用に最新日を取る銘柄（日経・代表ETF・流動株）。なければ他テーブルを試す
_AUTO_REF_CODES = ("0", "1306", "7203", "6758")


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
    "7": FetchSpec("10年", "year", 10),
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
    # 株式分割・配当を調整済みの系列を使う（未調整だと分割日に疑似暴落し損切りが誤発火する）
    df = ticker.history(period=period_str, interval="1d", auto_adjust=True)
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


def _truncate_table(cursor: sqlite3.Cursor, code: str) -> None:
    cursor.execute(f'DELETE FROM "tbl_{code}"')


def _pick_spec_with_menu() -> FetchSpec:
    print("株価更新期間を選んでください:")
    print("  0. 自動（過去1か月の欠損から選択）")
    for key, spec in MENU_SPECS.items():
        print(f"  {key}. {spec.label}")

    while True:
        choice = input("番号を入力してください [0-7]: ").strip()
        if choice in ("0", "auto"):
            return resolve_auto_spec()
        if choice in MENU_SPECS:
            return MENU_SPECS[choice]
        print("入力エラー: 0〜7 の番号を指定してください。")


def _last_weekday_on_or_before(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _parse_db_date(raw: object) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return pd.Timestamp(text).date()
    except (ValueError, TypeError):
        return None


def _pick_reference_table(cursor: sqlite3.Cursor, tables: set[str]) -> str | None:
    for code in _AUTO_REF_CODES:
        name = f"tbl_{code}"
        if name in tables:
            return name
    for name in sorted(tables):
        if name.startswith("tbl_") and name[4:].isdigit():
            return name
    return None


def _load_recent_dates(cursor: sqlite3.Cursor, table: str, since: date) -> set[date]:
    cursor.execute(
        f'SELECT DISTINCT datetime FROM "{table}" WHERE datetime >= ?',
        (since.isoformat(),),
    )
    out: set[date] = set()
    for (raw,) in cursor.fetchall():
        parsed = _parse_db_date(raw)
        if parsed is not None:
            out.add(parsed)
    return out


def calendar_gap_days_needing_fetch(
    existing_dates: set[date],
    *,
    today: date | None = None,
    lookback_days: int = AUTO_LOOKBACK_CALENDAR_DAYS,
) -> int:
    """参照系列の最新日がどれだけ古いか（暦日）を返す。

    過去 lookback 内にデータが全くない場合は lookback_days。
    祝日は平日扱いしないと誤検知するため、窓内の「穴」ではなく最新日の古さで判定する。
    """
    as_of = _last_weekday_on_or_before(today or date.today())
    window_start = as_of - timedelta(days=lookback_days - 1)
    in_window = {d for d in existing_dates if window_start <= d <= as_of}
    if not in_window:
        return lookback_days
    latest = max(in_window)
    if latest >= as_of:
        return 0
    return max(1, (as_of - latest).days)


def menu_key_for_gap_days(gap_days: int) -> str:
    """必要暦日数 → 既存メニュー番号。"""
    if gap_days <= 0:
        return "1"
    if gap_days <= 1:
        return "1"
    if gap_days <= 5:
        return "6"
    if gap_days <= 10:
        return "2"
    return "3"


def resolve_auto_spec(
    db_path: Path | None = None,
    *,
    today: date | None = None,
) -> FetchSpec:
    """DB の過去約1か月を見て取得期間を自動選択する。"""
    path = db_path or _resolve_db_path()
    if not path.exists():
        print(f"自動選択: DBなし → {MENU_SPECS['3'].label}")
        return MENU_SPECS["3"]

    as_of = _last_weekday_on_or_before(today or date.today())
    window_start = as_of - timedelta(days=AUTO_LOOKBACK_CALENDAR_DAYS - 1)

    conn = sqlite3.connect(path)
    try:
        cursor = conn.cursor()
        tables = _read_table_names(cursor)
        table = _pick_reference_table(cursor, tables)
        if table is None:
            print(f"自動選択: 参照テーブルなし → {MENU_SPECS['3'].label}")
            return MENU_SPECS["3"]

        existing = _load_recent_dates(cursor, table, window_start)
        gap = calendar_gap_days_needing_fetch(existing, today=as_of)
        key = menu_key_for_gap_days(gap)
        spec = MENU_SPECS[key]
        latest = max(existing) if existing else None
        latest_s = latest.isoformat() if latest else "なし"
        print(
            f"自動選択: 参照={table} 最新={latest_s} "
            f"必要約{gap}暦日 → メニュー{key} ({spec.label})"
        )
        return spec
    finally:
        conn.close()


def _pick_spec_from_args(choice: str | None) -> FetchSpec:
    if choice in ("0", "auto"):
        return resolve_auto_spec()
    if choice and choice in MENU_SPECS:
        return MENU_SPECS[choice]
    return _pick_spec_with_menu()


def run(spec: FetchSpec, sleep_sec: float = 0.1, *, full_replace: bool = False) -> int:
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

            if full_replace:
                _truncate_table(cursor, code)
            else:
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
        choices=["auto", "0", *MENU_SPECS.keys()],
        help="期間指定: auto/0=過去1か月の欠損から自動, 1=1日,2=10日,3=30日,4=100日,5=5年,6=5日,7=10年",
    )
    parser.add_argument(
        "--full-replace",
        action="store_true",
        help="各銘柄テーブルを全削除してから取得データで置換（分割調整後の全再構築向け）",
    )
    args = parser.parse_args()
    spec = _pick_spec_from_args(args.menu)
    return run(spec, full_replace=args.full_replace)
