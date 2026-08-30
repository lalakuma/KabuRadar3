"""OS 別ランチャー（bat / sh）のパスと実行."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from .paths import PROJECT_ROOT


def scripts_dir() -> Path:
    if platform.system() == "Windows":
        return PROJECT_ROOT / "bat"
    return PROJECT_ROOT / "sh"


def script_extension() -> str:
    return ".bat" if platform.system() == "Windows" else ".sh"


def script_path(base_name: str) -> Path:
    ext = script_extension()
    name = base_name if base_name.endswith(ext) else f"{base_name}{ext}"
    return scripts_dir() / name


def run_script(base_name: str, *args: str) -> int:
    path = script_path(base_name)
    if not path.is_file():
        print(f"Script not found: {path}", file=sys.stderr)
        return 127

    cwd = scripts_dir()
    if platform.system() == "Windows":
        completed = subprocess.run(
            [str(path), *args],
            cwd=str(cwd),
            shell=True,
            check=False,
        )
    else:
        completed = subprocess.run(
            ["bash", str(path), *args],
            cwd=str(cwd),
            check=False,
        )
    return int(completed.returncode)
