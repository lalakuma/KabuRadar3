#!/usr/bin/env python3
"""旧 KabuRadar (HI) のタスクスケジューラ登録を削除."""

from __future__ import annotations

import re
import subprocess
import sys


def _task_blocks(xml: str) -> list[tuple[str, str]]:
    """(task_uri, block_xml) のリスト。"""
    parts = re.split(r"<!-- (\\[^>]+) -->", xml)
    blocks: list[tuple[str, str]] = []
    for i in range(1, len(parts), 2):
        name = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        blocks.append((name, body))
    return blocks


def main() -> int:
    xml = subprocess.check_output(["schtasks", "/Query", "/XML"], text=True, errors="replace")
    legacy_patterns = (
        r"2-1\.kabu_screening_trade",
        r"main_param_chg\.py HI",
        r"config_hi\.ini",
    )
    targets: list[str] = []
    for name, body in _task_blocks(xml):
        cmd_match = re.search(r"<Command>([^<]+)</Command>", body, re.I)
        if not cmd_match:
            continue
        cmd = cmd_match.group(1)
        if "KabuRadar\\software" in cmd and "2-1.kabu_screening" in cmd:
            targets.append(name)

    if not targets:
        print("削除対象の旧 HI タスクは見つかりませんでした。")
        return 0

    rc = 0
    for name in targets:
        print(f"削除: {name}")
        result = subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"], capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr or result.stdout)
            rc = 1
        else:
            print("  OK")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
