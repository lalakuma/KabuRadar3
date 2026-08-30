from __future__ import annotations

from datetime import datetime

from kaburadar3.scheduling.slots import LOCAL_SLOTS, mark_slot_done, slots_due


def test_slots_due_in_window() -> None:
    slot = LOCAL_SLOTS[0]
    now = datetime.combine(datetime.today(), slot.at)
    due = slots_due(now, state={})
    assert any(s.slot_id == slot.slot_id for s in due)


def test_slots_not_due_after_mark_done(tmp_path, monkeypatch) -> None:
    from kaburadar3.scheduling import slots as slots_mod

    state_file = tmp_path / "state.json"
    monkeypatch.setattr(slots_mod, "STATE_FILE", state_file)

    slot = LOCAL_SLOTS[1]
    now = datetime.combine(datetime.today(), slot.at)
    mark_slot_done(slot.slot_id, now=now)
    due = slots_due(now)
    assert all(s.slot_id != slot.slot_id for s in due)
