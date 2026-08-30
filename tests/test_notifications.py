from __future__ import annotations

import json

import pandas as pd

from kaburadar3.notifications import line
from kaburadar3.notifications.summary import format_top_symbols


def test_format_top_symbols(tmp_path) -> None:
    df = pd.DataFrame(
        [
            {"code": "7203", "name": "トヨタ", "incomes": 5000, "winlose": "W1L0"},
            {"code": "6758", "name": "ソニー", "incomes": 3000, "winlose": "W0L1"},
        ]
    )
    csv_path = tmp_path / "Y0_PF1.0_W1L0_rate50.0_all8000.csv"
    from kaburadar3.settings.encoding import CSV_ENCODING

    df.to_csv(csv_path, encoding=CSV_ENCODING, index=False)

    lines = format_top_symbols(limit=5, results_dir=tmp_path)
    assert len(lines) == 2
    assert "7203" in lines[0]
    assert "5,000" in lines[0] or "5000" in lines[0]


def test_is_configured_false(monkeypatch) -> None:
    monkeypatch.setattr(line, "_get_env", lambda: ("", []))
    assert line.is_configured() is False


def test_notify_optional_skips_without_config(monkeypatch) -> None:
    monkeypatch.setattr(line, "_get_env", lambda: ("", []))
    assert line.notify_optional(["test"], "LO") is False


def test_notify_from_payload_empty_today(monkeypatch) -> None:
    monkeypatch.setattr(line, "notify_optional", lambda *_a, **_k: True)
    payload = {
        "mode": "LO",
        "today": {"trade_date": "2026-06-01", "new_buy": [], "sellback": []},
        "runtime": {"notify": {"today_buy": True, "today_sellback": True}},
        "line_events": [],
    }
    assert line.notify_from_payload(payload) is True
