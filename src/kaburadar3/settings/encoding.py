"""CSV エンコーディング（Windows・Linux 共通）."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# UTF-8 BOM: Excel で文字化けしにくく、Linux でも扱いやすい
CSV_ENCODING = "utf-8-sig"

# 過去の cp932 / shift_jis 出力を読むときのフォールバック（新規出力は UTF-8 BOM のみ）
LEGACY_CSV_ENCODINGS = ("cp932", "shift_jis", "ms932")


def read_csv(path: Path | str, **kwargs: Any) -> pd.DataFrame:
    """UTF-8 BOM を優先し、失敗時は旧エンコーディングを試す。"""
    path = Path(path)
    last_error: UnicodeDecodeError | None = None
    for encoding in (CSV_ENCODING, *LEGACY_CSV_ENCODINGS):
        try:
            return pd.read_csv(path, encoding=encoding, **kwargs)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return pd.read_csv(path, encoding=CSV_ENCODING, **kwargs)
