from __future__ import annotations

from pathlib import Path

import pandas as pd

from kaburadar3.settings.encoding import CSV_ENCODING
from kaburadar3.signals.daily_history import collect_daily_history


def _write_code_csv(path: Path, rows: list[tuple]) -> None:
    df = pd.DataFrame(rows, columns=["Index", "mark", "close", "buygain", "sellgain"])
    path.write_text(df.to_csv(index=False), encoding=CSV_ENCODING)


def test_collect_daily_history_groups_by_date(tmp_path: Path) -> None:
    _write_code_csv(
        tmp_path / "code1000_rsi.csv",
        [
            ("2026-06-01", "新買", 1000, 0, 0),
            ("2026-06-02", "返売", 1100, 0, 5000),
        ],
    )
    _write_code_csv(
        tmp_path / "code2000_rsi.csv",
        [
            ("2026-06-02", "新買", 2000, 0, 0),
        ],
    )
    result = collect_daily_history(tmp_path, {"1000": "銘柄A", "2000": "銘柄B"})
    assert len(result["days"]) == 2
    assert result["days"][0]["date"] == "2026-06-02"
    assert result["days"][0]["pnl"] == 5000
    assert result["days"][0]["new_buy_count"] == 1
    assert result["days"][0]["sellback_count"] == 1
    assert result["days"][0]["sellback"][0]["pnl"] == 5000
    assert result["days"][1]["date"] == "2026-06-01"
    assert result["days"][1]["new_buy_count"] == 1
    assert len(result["buy_days"]) == 2
    assert result["buy_days"][0]["date"] == "2026-06-02"


def test_ignores_zero_close_signals(tmp_path: Path) -> None:
    _write_code_csv(
        tmp_path / "code1000_rsi.csv",
        [
            ("2026-06-02", "新買", 0, 0, 0),
        ],
    )
    result = collect_daily_history(tmp_path)
    assert result["days"][0]["new_buy_count"] == 0
    assert result["buy_days"] == []
