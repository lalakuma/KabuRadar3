"""株価更新 + 解析（旧 screening_trade）。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from kaburadar3.config import PROJECT_ROOT

CLI_DIR = Path(__file__).resolve().parent


def _run_script(script: Path, *args: str) -> int:
    cmd = [sys.executable, str(script), *args]
    completed = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="株価更新後に全銘柄解析を実行")
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="株価更新をスキップして解析のみ実行",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="解析成功後に LINE へ集計サマリーを送信",
    )
    args = parser.parse_args()

    print(f"[{datetime.now().isoformat()}] screening: started")

    if not args.skip_update:
        rc = _run_script(CLI_DIR / "update_prices.py", "--menu", "6")
        if rc != 0:
            print(f"screening: update_prices failed with code {rc}")
            return rc

    analyze_args: list[str] = []
    if args.notify:
        analyze_args.append("--notify")
    rc = _run_script(CLI_DIR / "analyze.py", *analyze_args)
    if rc != 0:
        print(f"screening: analyze failed with code {rc}")
        return rc

    print(f"[{datetime.now().isoformat()}] screening: completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
