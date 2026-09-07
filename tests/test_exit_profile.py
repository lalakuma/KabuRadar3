from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from kaburadar3.settings.runtime import (
    EXIT_PROFILE_PROFIT,
    EXIT_PROFILE_WINRATE,
    RuntimeConfig,
    apply_exit_profile_to_judge,
    load_runtime_config,
)
from kaburadar3.strategy.models import Judge


def test_load_exit_profile(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "runtime.json"
    path.write_text(
        json.dumps({"exit_strategy": {"profile": "winrate"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    cfg = load_runtime_config(path)
    assert cfg.exit_profile == EXIT_PROFILE_WINRATE


def test_apply_exit_profile_to_judge(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "runtime.json"
    jg = SimpleNamespace(rsi60_hold_rci_up=0)

    path.write_text(json.dumps({"exit_strategy": {"profile": "profit"}}), encoding="utf-8")
    monkeypatch.setattr("kaburadar3.settings.runtime.RUNTIME_FILE", path)
    apply_exit_profile_to_judge(jg)
    assert jg.rsi60_hold_rci_up == 1

    path.write_text(json.dumps({"exit_strategy": {"profile": "winrate"}}), encoding="utf-8")
    apply_exit_profile_to_judge(jg)
    assert jg.rsi60_hold_rci_up == 0


def test_judge_uses_runtime_profile(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps({"exit_strategy": {"profile": "winrate"}}), encoding="utf-8")
    monkeypatch.setattr("kaburadar3.settings.runtime.RUNTIME_FILE", path)
    jg = Judge("SCREENING")
    assert jg.rsi60_hold_rci_up == 0

    path.write_text(json.dumps({"exit_strategy": {"profile": "profit"}}), encoding="utf-8")
    jg = Judge("SCREENING")
    assert jg.rsi60_hold_rci_up == 1
