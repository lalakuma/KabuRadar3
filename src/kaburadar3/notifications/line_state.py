"""LINE 通知の1日1回制御."""

from __future__ import annotations

import json
from pathlib import Path

from kaburadar3.settings.paths import PROJECT_ROOT

STATE_FILE = PROJECT_ROOT / "data" / "line_notify_state.json"


def load_state(path: Path | None = None) -> dict[str, str]:
    target = path or STATE_FILE
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, str], path: Path | None = None) -> None:
    target = path or STATE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def already_notified(trade_date: str, path: Path | None = None) -> bool:
    if not trade_date or trade_date == "—":
        return False
    state = load_state(path)
    return state.get("last_trade_date") == trade_date


def mark_notified(trade_date: str, path: Path | None = None) -> None:
    if not trade_date or trade_date == "—":
        return
    state = load_state(path)
    state["last_trade_date"] = trade_date
    save_state(state, path)
