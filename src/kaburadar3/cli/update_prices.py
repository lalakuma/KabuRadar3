"""CLI: 株価更新."""

from __future__ import annotations

import sys
from pathlib import Path

# スクリプト直接実行時の PYTHONPATH 補助
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from kaburadar3.market_data.prices import main

if __name__ == "__main__":
    raise SystemExit(main())
