from __future__ import annotations

from pathlib import Path

import pytest

from kaburadar3.config import CONFIG_HI, CONFIG_LO, PROJECT_ROOT, read_config, resolve_path_value
from kaburadar3.settings import screening as conf


def test_config_lo_exists() -> None:
    assert CONFIG_LO.exists()


def test_config_hi_exists() -> None:
    assert CONFIG_HI.exists()


def test_read_screening_rsi4() -> None:
    assert read_config("SCREENING", "SCR_JDG_RSI4", config_path=CONFIG_LO) == "1"


def test_config_hi_rsi4rev() -> None:
    assert read_config("SCREENING", "SCR_JDG_RSI4REV", config_path=CONFIG_HI) == "1"
    assert read_config("SCREENING", "SCR_JDG_RSI4REV", config_path=CONFIG_LO) == "0"


def test_resolve_path_db() -> None:
    raw = read_config("DATABASE", "PATH_DB", config_path=CONFIG_LO)
    path = resolve_path_value(raw)
    assert path == (PROJECT_ROOT / "data" / "kaburadar.db").resolve()


def test_config_stance() -> None:
    assert conf.config_stance(CONFIG_LO) == "LO"
    assert conf.config_stance(CONFIG_HI) == "HI"


def test_resolve_config_path_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KABURADAR_CONFIG", "config/config_hi.ini")
    assert conf.resolve_config_path() == CONFIG_HI.resolve()
