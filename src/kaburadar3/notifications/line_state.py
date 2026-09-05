"""LINE 通知のスロット単位重複防止（1日3スロットそれぞれ1通）."""

from __future__ import annotations

import json
from pathlib import Path

from kaburadar3.settings.paths import PROJECT_ROOT

STATE_FILE = PROJECT_ROOT / "data" / "line_notify_state.json"


def _notify_key(trade_date: str, slot_id: str) -> str:
    slot = slot_id.strip() or "manual"
    return f"{trade_date}:{slot}"


def load_state(path: Path | None = None) -> dict[str, list[str]]:
    target = path or STATE_FILE
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("notified"), list):
            return {"notified": [str(x) for x in data["notified"]]}
        if isinstance(data, dict) and "last_trade_date" in data:
            # 旧形式からの移行
            old = str(data.get("last_trade_date", ""))
            return {"notified": [f"{old}:legacy"]} if old else {}
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, list[str]], path: Path | None = None) -> None:
    target = path or STATE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"notified": list(state.get("notified", []))}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def already_notified(trade_date: str, slot_id: str = "", path: Path | None = None) -> bool:
    if not trade_date or trade_date == "—":
        return False
    key = _notify_key(trade_date, slot_id)
    state = load_state(path)
    return key in state.get("notified", [])


def mark_notified(trade_date: str, slot_id: str = "", path: Path | None = None) -> None:
    if not trade_date or trade_date == "—":
        return
    key = _notify_key(trade_date, slot_id)
    state = load_state(path)
    items = list(state.get("notified", []))
    if key not in items:
        items.append(key)
    state["notified"] = items
    save_state(state, path)
