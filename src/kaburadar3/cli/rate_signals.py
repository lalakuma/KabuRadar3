"""シグナル銘柄の Gemini 評価 CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from kaburadar3.qualitative.rater import rate_symbol


def main() -> int:
    parser = argparse.ArgumentParser(description="Rate a symbol with Gemini")
    parser.add_argument("--code", required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--signal", default="新買")
    parser.add_argument("--date", default="")
    args = parser.parse_args()

    rating = rate_symbol(
        code=args.code,
        name=args.name,
        signal=args.signal,
        trade_date=args.date or None,
        use_cache=False,
    )
    print(json.dumps(rating.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
