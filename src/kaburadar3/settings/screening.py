"""SCREENING / SHUUKEI セクション向けのレガシー互換 API."""

from __future__ import annotations

import errno
import os
import shutil
from pathlib import Path

from .loader import read_config, resolve_path_value
from .paths import CONFIG_DIR, CONFIG_HI, CONFIG_LO, PROJECT_ROOT

CONF_SEC_SCR = "SCREENING"
CONF_SEC_SHUUKEI = "SHUUKEI"
CONF_SEC_DATABASE = "DATABASE"

CONF_KEY_JDG_RSI4 = "SCR_JDG_RSI4"
CONF_KEY_JDG_RSI4REV = "SCR_JDG_RSI4REV"
CONF_KEY_JDG_RSVENT = "SCR_JDG_RSVENT"
CONF_KEY_JDG_RCI = "SCR_JDG_RCI"
CONF_KEY_SCR_RCI_PERIOD = "SCR_RCI_PERIOD"
CONF_KEY_SCR_RCI_LOW = "SCR_RCI_LOW"
CONF_KEY_SCR_RCI_TURN_MIN = "SCR_RCI_TURN_MIN"
CONF_KEY_SCR_RCI_LOOKBACK = "SCR_RCI_LOOKBACK"
CONF_KEY_JDG_RCI_SEQ = "SCR_JDG_RCI_SEQ"
CONF_KEY_SCR_RCI_PREP_MAX_BARS = "SCR_RCI_PREP_MAX_BARS"
CONF_KEY_JDG_RCI_EXIT = "SCR_JDG_RCI_EXIT"
CONF_KEY_SCR_RCI_EXIT_TURN_MIN = "SCR_RCI_EXIT_TURN_MIN"
CONF_KEY_SCR_RCI_EXIT_PEAK = "SCR_RCI_EXIT_PEAK"
CONF_KEY_JDG_STOP_LOSS = "SCR_JDG_STOP_LOSS"
CONF_KEY_SCR_STOP_LOSS_PCT = "SCR_STOP_LOSS_PCT"

CONF_KEY_SCR_SELLBUY = "SCR_SELLBUY"
CONF_KEY_SCR_ENT_TIMING = "SCR_ENT_TIMING"
CONF_KEY_SCR_PAST_PERIOD = "SCR_PAST_PERIOD"
CONF_KEY_SCR_SELL_PERIOD = "SCR_SELL_PERIOD"
CONF_KEY_SCR_RSI_MAX = "SCR_RSI_MAX"
CONF_KEY_SCR_RSI_BORDER = "SCR_RSI_BORDER"
CONF_KEY_SCR_RSI_PER = "SCR_RSI_PER"
CONF_KEY_SCR_RSI_PERIOD = "SCR_RSI_PERIOD"
CONF_KEY_SCR_SRSI_HI = "SCR_SRSI_HI"
CONF_KEY_SCR_SRSI_LOW = "SCR_SRSI_LOW"
CONF_KEY_SCR_ENTRY_REST = "SCR_ENTRY_REST"
CONF_KEY_PATH_SHUUKEI = "PATH_SHUUKEI"
CONF_KEY_PATH_HONBAN = "PATH_HONBAN"
CONF_KEY_PATH_DB = "PATH_DB"

_PATH_KEYS = frozenset(
    {
        CONF_KEY_PATH_SHUUKEI,
        CONF_KEY_PATH_HONBAN,
        CONF_KEY_PATH_DB,
    }
)


def _as_legacy_dir(path: Path) -> str:
    text = str(path)
    if not text.endswith(("\\", "/")):
        text += os.sep
    return text


def resolve_config_path() -> Path:
    """有効な設定 ini。KABURADAR_CONFIG または config_lo.ini。"""
    raw = os.getenv("KABURADAR_CONFIG", "").strip()
    if raw:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        if candidate.is_file():
            return candidate
    if CONFIG_LO.exists():
        return CONFIG_LO
    raise FileNotFoundError(f"config ini not found in: {CONFIG_DIR}")


def config_stance(config_path: Path | None = None) -> str:
    """config_hi.ini → HI、それ以外 → LO。"""
    path = config_path or resolve_config_path()
    if path.name.endswith("_hi.ini"):
        return "HI"
    return "LO"


def get_confFilePath() -> str:
    return str(resolve_config_path())


def get_config(section: str, key: str, default: str | None = None) -> str:
    config_path = resolve_config_path()
    if not config_path.exists():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(config_path))
    try:
        raw = read_config(section, key, config_path=config_path)
    except Exception:
        if default is not None:
            return default
        raise
    if key in _PATH_KEYS:
        resolved = resolve_path_value(raw)
        if key == CONF_KEY_PATH_DB:
            return str(resolved)
        return _as_legacy_dir(resolved)
    return raw


def copy_confFile(destpath: str) -> None:
    config_path = resolve_config_path()
    if not config_path.exists():
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(config_path))
    dest = Path(destpath)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(config_path, dest / config_path.name)
