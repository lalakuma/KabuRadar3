"""既存 KabuRadar (v1) の software/src/line.py から LINE 設定を読み取り移植する.

使い方（プロジェクトルートで）:
  python scripts/sync_line_from_kaburadar.py --env
  python scripts/sync_line_from_kaburadar.py --gh-secrets

トークンは標準出力に出しません。
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LINE_PY = Path.home() / "AppData/Local/Temp/KabuRadar-src/software/src/line.py"


def _parse_line_py(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    token_match = re.search(r'CHANNEL_ACCESS_TOKEN\s*=\s*"([^"]+)"', text)
    users_match = re.search(r"USER_IDS\s*=\s*(\[[^\]]+\])", text)
    if not token_match or not users_match:
        raise ValueError(f"line.py の形式を解釈できません: {path}")
    token = token_match.group(1).strip()
    user_list = ast.literal_eval(users_match.group(1))
    if not token or not user_list:
        raise ValueError("トークンまたは USER_IDS が空です")
    user_ids = ",".join(str(u).strip() for u in user_list if str(u).strip())
    return token, user_ids


def _write_env(token: str, user_ids: str) -> Path:
    env_path = PROJECT_ROOT / ".env"
    lines: list[str] = []
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key = line.split("=", 1)[0].strip() if "=" in line else ""
            if key in ("LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_IDS"):
                continue
            lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(f"LINE_CHANNEL_ACCESS_TOKEN={token}")
    lines.append(f"LINE_USER_IDS={user_ids}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return env_path


def _set_gh_secrets(token: str, user_ids: str, repo: str) -> None:
    subprocess.run(
        ["gh", "secret", "set", "LINE_CHANNEL_ACCESS_TOKEN", "-R", repo, "-b", token],
        check=True,
    )
    subprocess.run(
        ["gh", "secret", "set", "LINE_USER_IDS", "-R", repo, "-b", user_ids],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="KabuRadar v1 から LINE 設定を移植")
    parser.add_argument(
        "--line-py",
        type=Path,
        default=DEFAULT_LINE_PY,
        help="v1 の line.py パス",
    )
    parser.add_argument("--env", action="store_true", help=".env に書き込む")
    parser.add_argument("--gh-secrets", action="store_true", help="GitHub Secrets に登録")
    parser.add_argument(
        "--repo",
        default="lalakuma/KabuRadar3",
        help="gh secret 先リポジトリ",
    )
    args = parser.parse_args()
    if not args.env and not args.gh_secrets:
        parser.error("--env または --gh-secrets を指定してください")

    line_py = args.line_py.expanduser().resolve()
    if not line_py.is_file():
        print(f"line.py が見つかりません: {line_py}", file=sys.stderr)
        print("先に: git clone https://github.com/lalakuma/KabuRadar.git を実行するか --line-py を指定", file=sys.stderr)
        return 1

    token, user_ids = _parse_line_py(line_py)
    if args.env:
        path = _write_env(token, user_ids)
        print(f"Wrote {path} (LINE のみ更新)")
    if args.gh_secrets:
        _set_gh_secrets(token, user_ids, args.repo)
        print(f"GitHub Secrets 登録完了: {args.repo}")
        print("  LINE_CHANNEL_ACCESS_TOKEN")
        print("  LINE_USER_IDS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
