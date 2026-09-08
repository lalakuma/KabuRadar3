"""CLI: GitHub Pages 用 JSON 公開."""

from __future__ import annotations

import argparse
import os

from kaburadar3.publishing.github_pages import publish, push_to_github


def main() -> int:
    parser = argparse.ArgumentParser(description="解析結果を GitHub Pages 用 JSON に書き出す")
    parser.add_argument(
        "--push",
        action="store_true",
        help="docs/data.json を commit して origin へ push（ブランチは自動検出または .env）",
    )
    args = parser.parse_args()

    if args.push:
        os.environ["KABURADAR_REFRESH_TIMESTAMP"] = "1"

    payload = publish()
    if args.push:
        return push_to_github(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
