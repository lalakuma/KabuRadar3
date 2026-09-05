#!/usr/bin/env python3
"""旧 KabuRadar (HI/LO 形式) の LINE 通知を無効化する。

KabuRadar3 の ★付き通知だけ残す用途。line.py の先頭で早期 return するガードを入れる。
"""

from __future__ import annotations

import sys
from pathlib import Path

LEGACY_LINE = Path(r"C:\share\MorinoFolder\Python\KabuRadar\software\src\line.py")
GUARD_MARKER = "KABURADAR3_LEGACY_LINE_OFF"
GUARD_BLOCK = f'''
# {GUARD_MARKER} — KabuRadar3 のみ LINE 通知する
def line_notify(lst_codes, stance):
    print("LINE: 旧 KabuRadar 通知は無効です（KabuRadar3 を使用）")
    return
'''


def main() -> int:
    if not LEGACY_LINE.is_file():
        print(f"ファイルがありません: {LEGACY_LINE}", file=sys.stderr)
        return 1

    text = LEGACY_LINE.read_text(encoding="utf-8")
    if GUARD_MARKER in text:
        print("既に無効化済みです。")
        return 0

    # 既存の line_notify 関数をガード版で置換
    import re

    new_text, n = re.subn(
        r"def line_notify\(lst_codes, stance\):[\s\S]*?(?=\n(?:def |$))",
        GUARD_BLOCK.strip() + "\n\n",
        text,
        count=1,
    )
    if n != 1:
        print("line_notify 関数が見つかりません。手動で無効化してください。", file=sys.stderr)
        return 1

    LEGACY_LINE.write_text(new_text, encoding="utf-8")
    print(f"無効化しました: {LEGACY_LINE}")
    print("旧 HI/LO 形式の LINE は送信されなくなります。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
