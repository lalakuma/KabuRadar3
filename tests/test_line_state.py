from __future__ import annotations

from kaburadar3.notifications import line_state


def test_line_notify_dedupe_per_slot(tmp_path) -> None:
    path = tmp_path / "line_notify_state.json"
    assert not line_state.already_notified("2026-09-02", "lo_1130", path)
    line_state.mark_notified("2026-09-02", "lo_1130", path)
    assert line_state.already_notified("2026-09-02", "lo_1130", path)
    assert not line_state.already_notified("2026-09-02", "lo_1500", path)
    line_state.mark_notified("2026-09-02", "lo_1500", path)
    assert line_state.already_notified("2026-09-02", "lo_1500", path)


def test_line_notify_manual_dedupe(tmp_path) -> None:
    path = tmp_path / "line_notify_state.json"
    line_state.mark_notified("2026-09-02", "", path)
    assert line_state.already_notified("2026-09-02", "", path)
