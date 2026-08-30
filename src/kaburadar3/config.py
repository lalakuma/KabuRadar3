"""後方互換: 設定は kaburadar.settings に集約."""

from kaburadar3.settings.loader import (
    copy_config_snapshot,
    project_path,
    read_config,
    read_path_config,
    resolve_path_value,
)
from kaburadar3.settings.paths import (
    CONFIG_DIR,
    CONFIG_HI,
    CONFIG_LO,
    DATA_DIR,
    DOCS_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
)

__all__ = [
    "CONFIG_DIR",
    "CONFIG_HI",
    "CONFIG_LO",
    "DATA_DIR",
    "DOCS_DIR",
    "LOG_DIR",
    "OUTPUT_DIR",
    "PROJECT_ROOT",
    "copy_config_snapshot",
    "project_path",
    "read_config",
    "read_path_config",
    "resolve_path_value",
]
