from __future__ import annotations

import pandas as pd

from kaburadar3.settings.encoding import CSV_ENCODING, read_csv


def test_csv_encoding_is_utf8_bom() -> None:
    assert CSV_ENCODING == "utf-8-sig"


def test_read_csv_utf8_bom(tmp_path) -> None:
    path = tmp_path / "sample.csv"
    df = pd.DataFrame({"code": ["7203"], "name": ["テスト"]})
    df.to_csv(path, encoding=CSV_ENCODING, index=False)
    loaded = read_csv(path)
    assert loaded.iloc[0]["name"] == "テスト"


def test_read_csv_legacy_cp932(tmp_path) -> None:
    path = tmp_path / "legacy.csv"
    df = pd.DataFrame({"code": ["7203"], "name": ["テスト"]})
    df.to_csv(path, encoding="cp932", index=False)
    loaded = read_csv(path)
    assert loaded.iloc[0]["name"] == "テスト"
