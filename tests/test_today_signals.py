from __future__ import annotations

from pathlib import Path

import pandas as pd

from kaburadar3.settings.encoding import CSV_ENCODING
from kaburadar3.signals.today import collect_today_signals


def _write_code_csv(path: Path, code: str, rows: list[tuple[str, str, float]]) -> None:
    df = pd.DataFrame(rows, columns=["Index", "mark", "close"])
    path.write_text(df.to_csv(index=False), encoding=CSV_ENCODING)


def test_collect_today_signals_latest_day(tmp_path: Path) -> None:
    _write_code_csv(
        tmp_path / "code1000_rsi.csv",
        "1000",
        [
            ("2026-06-01", "継続", 1000),
            ("2026-06-02", "新買", 1010),
        ],
    )
    _write_code_csv(
        tmp_path / "code2000_rsi.csv",
        "2000",
        [
            ("2026-06-02", "返売", 2000),
        ],
    )
    _write_code_csv(
        tmp_path / "code3000_rsi.csv",
        "3000",
        [
            ("2026-06-01", "新買", 500),
        ],
    )
    result = collect_today_signals(tmp_path, {"1000": "銘柄A", "2000": "銘柄B"})
    assert result["trade_date"] == "2026-06-02"
    assert result["new_buy_count"] == 1
    assert result["new_buy"][0]["code"] == "1000"
    assert result["sellback"][0]["code"] == "2000"


def test_ignores_historical_new_buy_when_last_row_is_hold(tmp_path: Path) -> None:
    _write_code_csv(
        tmp_path / "code1000_rsi.csv",
        "1000",
        [
            ("2026-06-01", "新買", 1000),
            ("2026-06-02", "継続", 1010),
        ],
    )
    _write_code_csv(
        tmp_path / "code2000_rsi.csv",
        "2000",
        [
            ("2026-06-02", "返売", 2000),
        ],
    )
    result = collect_today_signals(tmp_path)
    assert result["trade_date"] == "2026-06-02"
    assert result["new_buy_count"] == 0
    assert result["sellback"][0]["code"] == "2000"


def test_ignores_zero_close(tmp_path: Path) -> None:
    _write_code_csv(
        tmp_path / "code1000_rsi.csv",
        "1000",
        [
            ("2026-06-02", "新買", 0),
        ],
    )
    result = collect_today_signals(tmp_path)
    assert result["new_buy_count"] == 0
