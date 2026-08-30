"""CLI: docs/data.json から LINE 通知."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from kaburadar3.notifications.line import notify_from_payload
from kaburadar3.settings.paths import DOCS_DIR


def main() -> int:
    data_file = DOCS_DIR / "data.json"
    if not data_file.is_file():
        print(f"LINE: {data_file} がありません。", file=sys.stderr)
        return 1
    payload = json.loads(data_file.read_text(encoding="utf-8"))
    notify_from_payload(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
