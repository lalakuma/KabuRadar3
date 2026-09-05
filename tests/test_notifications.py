from __future__ import annotations

import json

import pandas as pd

from kaburadar3.notifications import line
from kaburadar3.notifications import line_state
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


def test_notify_from_payload_empty_today(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("kaburadar3.notifications.line_state.STATE_FILE", tmp_path / "line.json")
    monkeypatch.setattr(line, "notify_optional", lambda *_a, **_k: True)
    payload = {
        "mode": "LO",
        "today": {"trade_date": "2026-06-01", "new_buy": [], "sellback": []},
        "runtime": {"notify": {"today_buy": True, "today_sellback": True}},
        "line_events": [],
    }
    assert line.notify_from_payload(payload) is True


def test_format_stars() -> None:
    assert line.format_stars(5) == "★★★★★"
    assert line.format_stars(4) == "★★★★☆"
    assert line.format_stars(None) == ""


def test_format_signal_row_includes_stars() -> None:
    row = {
        "code": "7532",
        "name": "パン・パシフィックHD",
        "close": 769,
        "quality": {"stars": 4},
    }
    text = line.format_signal_row(row)
    assert "7532" in text
    assert "★★★★☆" in text
    assert "¥769" in text


def test_notify_from_payload_skips_duplicate_slot(monkeypatch, tmp_path) -> None:
    state_path = tmp_path / "line_notify_state.json"
    monkeypatch.setattr("kaburadar3.notifications.line_state.STATE_FILE", state_path)
    monkeypatch.setenv("KABURADAR_SLOT_ID", "lo_1130")
    line_state.mark_notified("2026-09-02", "lo_1130", state_path)

    called = False

    def _notify(*_a, **_k):
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(line, "notify_optional", _notify)
    payload = {
        "mode": "LO",
        "today": {"trade_date": "2026-09-02", "new_buy": [], "sellback": []},
        "runtime": {"notify": {"today_buy": True, "today_sellback": True}},
        "line_events": [],
    }
    assert line.notify_from_payload(payload) is False
    assert called is False
    assert not line_state.already_notified("2026-09-02", "lo_1500", state_path)


def test_notify_from_payload_includes_stars(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("kaburadar3.notifications.line_state.STATE_FILE", tmp_path / "line.json")
    captured: list[str] = []

    def _capture(body, _stance: str) -> bool:
        captured.extend(body)
        return True

    monkeypatch.setattr(line, "notify_optional", _capture)
    payload = {
        "mode": "LO",
        "today": {
            "trade_date": "2026-09-02",
            "new_buy": [
                {
                    "code": "7532",
                    "name": "パン・パシフィックHD",
                    "close": 769,
                    "quality": {"stars": 4},
                }
            ],
            "sellback": [],
        },
        "runtime": {"notify": {"today_buy": True, "today_sellback": False}},
        "line_events": [],
    }
    assert line.notify_from_payload(payload) is True
    assert any("★★★★☆" in item for item in captured)
    assert any(item.startswith("詳細: ") and "github.io/KabuRadar3" in item for item in captured)
    assert sum(1 for item in captured if item.startswith("詳細: ")) == 1
