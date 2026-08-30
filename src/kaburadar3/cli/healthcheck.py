"""環境・設定の簡易チェック（個人運用向け）."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kaburadar3.config import CONFIG_LO, PROJECT_ROOT, read_config, resolve_path_value
from kaburadar3.notifications.line import is_configured


def _check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "OK" if ok else "NG"
    line = f"  [{mark}] {name}"
    if detail:
        line += f" - {detail}"
    print(line)
    return ok


def run(*, require_db: bool) -> int:
    print(f"KabuRadar3 healthcheck ({PROJECT_ROOT})")
    all_ok = True

    all_ok &= _check("config_lo.ini", CONFIG_LO.is_file(), str(CONFIG_LO))
    try:
        rsi4 = read_config("SCREENING", "SCR_JDG_RSI4", config_path=CONFIG_LO)
        all_ok &= _check("SCR_JDG_RSI4", rsi4 == "1", f"value={rsi4}")
    except Exception as exc:  # noqa: BLE001
        all_ok &= _check("config read", False, str(exc))

    try:
        db_path = resolve_path_value(read_config("DATABASE", "PATH_DB", config_path=CONFIG_LO))
        db_ok = db_path.is_file()
        if require_db:
            all_ok &= _check("database", db_ok, str(db_path))
        else:
            _check("database", db_ok, str(db_path) + (" (optional)" if not db_ok else ""))
    except Exception as exc:  # noqa: BLE001
        all_ok &= _check("database path", False, str(exc))

    results = PROJECT_ROOT / "output" / "results"
    _check("output/results", results.is_dir(), "mkdir on first analyze" if not results.is_dir() else "")

    line_ok = is_configured()
    _check("LINE (.env)", True, "configured" if line_ok else "not set (optional)")

    src = PROJECT_ROOT / "src" / "kaburadar3" / "cli" / "analyze.py"
    all_ok &= _check("cli/analyze.py", src.is_file())

    print()
    if all_ok:
        print("All required checks passed.")
        return 0
    print("Some checks failed.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="KabuRadar3 環境チェック")
    parser.add_argument(
        "--require-db",
        action="store_true",
        help="DB ファイル必須（無いと終了コード 1）",
    )
    args = parser.parse_args()
    return run(require_db=args.require_db)


if __name__ == "__main__":
    raise SystemExit(main())
