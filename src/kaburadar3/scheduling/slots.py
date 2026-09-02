"""ローカル実行スロット定義と実行状態."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from kaburadar3.settings.paths import PROJECT_ROOT

STATE_FILE = PROJECT_ROOT / "data" / "local_schedule_state.json"


@dataclass(frozen=True)
class LocalSlot:
    slot_id: str
    label: str
    at: time
    window_minutes: int
    config: str
    script: str

    def window_start(self, day: date) -> datetime:
        return datetime.combine(day, self.at)

    def window_end(self, day: date) -> datetime:
        return self.window_start(day) + timedelta(minutes=self.window_minutes)


LOCAL_SLOTS: tuple[LocalSlot, ...] = (
    LocalSlot(
        slot_id="lo_1130",
        label="11:30 LO（場中）",
        at=time(11, 30),
        window_minutes=10,
        config="config/config_lo.ini",
        script="screening_lo",
    ),
    LocalSlot(
        slot_id="lo_1500",
        label="15:00 LO（場中）",
        at=time(15, 0),
        window_minutes=10,
        config="config/config_lo.ini",
        script="screening_lo",
    ),
    LocalSlot(
        slot_id="lo_1600",
        label="16:00 LO（引け後）",
        at=time(16, 0),
        window_minutes=15,
        config="config/config_lo.ini",
        script="screening_lo",
    ),
)


def load_state(path: Path | None = None) -> dict[str, list[str]]:
    target = path or STATE_FILE
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, list[str]], path: Path | None = None) -> None:
    target = path or STATE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def is_slot_done(slot_id: str, now: datetime | None = None, state: dict[str, list[str]] | None = None) -> bool:
    now = now or datetime.now()
    state = state if state is not None else load_state()
    return slot_id in state.get(now.date().isoformat(), [])


def slots_due(now: datetime | None = None, state: dict[str, list[str]] | None = None) -> list[LocalSlot]:
    now = now or datetime.now()
    day_key = now.date().isoformat()
    state = state if state is not None else load_state()
    done = set(state.get(day_key, []))
    due: list[LocalSlot] = []
    for slot in LOCAL_SLOTS:
        if slot.slot_id in done:
            continue
        start = slot.window_start(now.date())
        end = slot.window_end(now.date())
        if start <= now <= end:
            due.append(slot)
    return due


def mark_slot_done(slot_id: str, now: datetime | None = None, state: dict[str, list[str]] | None = None) -> None:
    now = now or datetime.now()
    day_key = now.date().isoformat()
    state = dict(state if state is not None else load_state())
    items = list(state.get(day_key, []))
    if slot_id not in items:
        items.append(slot_id)
    state[day_key] = items
    save_state(state)
