"""プロジェクトのディレクトリ定数."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_LO = CONFIG_DIR / "config_lo.ini"
CONFIG_HI = CONFIG_DIR / "config_hi.ini"
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_DIR = OUTPUT_DIR / "logs"
DOCS_DIR = PROJECT_ROOT / "docs"
