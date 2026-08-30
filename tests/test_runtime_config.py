from __future__ import annotations

import json
from pathlib import Path

from kaburadar3.settings.runtime import RuntimeConfig, load_runtime_config


def test_load_runtime_defaults(tmp_path: Path) -> None:
    cfg = load_runtime_config(tmp_path / "missing.json")
    assert cfg.min_new_buy_count == 7
    assert cfg.etf_default == "1306"
    assert cfg.notify_today_buy is True


def test_load_runtime_from_file(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    path.write_text(
        json.dumps({"special_buy": {"min_new_buy_count": 8, "exit_rsi": 65}}, ensure_ascii=False),
        encoding="utf-8",
    )
    cfg = load_runtime_config(path)
    assert cfg.min_new_buy_count == 8
    assert cfg.exit_rsi == 65.0
    assert cfg.etf_default == "1306"
