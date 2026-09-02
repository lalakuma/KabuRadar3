from __future__ import annotations

from kaburadar3.notifications import line_state


def test_line_notify_dedupe(tmp_path) -> None:
    path = tmp_path / "line_notify_state.json"
    assert not line_state.already_notified("2026-09-02", path)
    line_state.mark_notified("2026-09-02", path)
    assert line_state.already_notified("2026-09-02", path)
    assert not line_state.already_notified("2026-09-03", path)
