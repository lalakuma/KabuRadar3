from __future__ import annotations

from pathlib import Path

from kaburadar3.settings.paths import PROJECT_ROOT
from kaburadar3.settings.scripts import script_extension, script_path, scripts_dir

EXPECTED = (
    "analyze",
    "update_prices",
    "screening",
    "publish",
    "analyze_and_publish",
    "healthcheck",
    "screening_notify",
    "run_scheduler",
)


def test_linux_shell_scripts_exist() -> None:
    sh_dir = PROJECT_ROOT / "sh"
    assert sh_dir.is_dir()
    for name in EXPECTED:
        path = sh_dir / f"{name}.sh"
        assert path.is_file(), f"missing {path}"


def test_script_path_uses_sh_on_non_windows(monkeypatch) -> None:
    monkeypatch.setattr("kaburadar3.settings.scripts.platform.system", lambda: "Linux")
    assert script_extension() == ".sh"
    assert scripts_dir() == PROJECT_ROOT / "sh"
    assert script_path("screening").name == "screening.sh"


def test_script_path_uses_bat_on_windows(monkeypatch) -> None:
    monkeypatch.setattr("kaburadar3.settings.scripts.platform.system", lambda: "Windows")
    assert script_extension() == ".bat"
    assert scripts_dir() == PROJECT_ROOT / "bat"
    assert script_path("screening").name == "screening.bat"
