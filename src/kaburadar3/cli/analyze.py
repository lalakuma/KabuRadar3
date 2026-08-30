"""CLI: 全銘柄バックテスト解析."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from kaburadar3.notifications.line import notify_analysis_summary
from kaburadar3.pipeline.analyze import run
from kaburadar3.settings.paths import PROJECT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="全銘柄バックテスト解析")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="設定 ini（例: config/config_hi.ini）。未指定時は config_lo.ini",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="完了後に GitHub Pages 用 JSON を生成し push する",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="成功時に LINE へ集計サマリーを送信（.env 設定時）",
    )
    args = parser.parse_args()

    if args.config:
        os.environ["KABURADAR_CONFIG"] = args.config

    rc = run()
    if rc != 0:
        return rc

    if args.notify:
        notify_analysis_summary()

    if not args.publish:
        return rc

    cmd = [sys.executable, str(Path(__file__).parent / "publish.py"), "--push"]
    completed = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
