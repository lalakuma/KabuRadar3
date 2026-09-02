"""CLI: docs/data.json から LINE 通知."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kaburadar3.notifications.line import notify_from_payload
from kaburadar3.settings.paths import DOCS_DIR


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="docs/data.json から LINE 通知")
    parser.add_argument(
        "--force",
        action="store_true",
        help="同日送信済みでも再送する",
    )
    args = parser.parse_args(argv)

    data_file = DOCS_DIR / "data.json"
    if not data_file.is_file():
        print(f"LINE: {data_file} がありません。", file=sys.stderr)
        return 1
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    if not notify_from_payload(payload, force=args.force):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
