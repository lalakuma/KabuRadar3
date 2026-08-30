from __future__ import annotations

import json

from kaburadar3.publishing import github_pages as publish
from kaburadar3.config import read_path_config


def test_build_payload_keys() -> None:
    results_dir = read_path_config("SHUUKEI", "PATH_HONBAN")
    if not results_dir.is_dir() or not list(results_dir.glob("Y*_PF*.csv")):
        return
    payload = publish.build_payload()
    assert payload["mode"] == "LO"
    assert "summary" in payload
    assert "symbols" in payload


def test_publish_writes_json(tmp_path, monkeypatch) -> None:
    results_dir = read_path_config("SHUUKEI", "PATH_HONBAN")
    if not results_dir.is_dir() or not list(results_dir.glob("Y*_PF*.csv")):
        return
    docs = tmp_path / "docs"
    monkeypatch.setattr(publish, "DOCS_DIR", docs)
    monkeypatch.setattr(publish, "DATA_FILE", docs / "data.json")
    payload = publish.publish()
    assert (docs / "data.json").exists()
    data = json.loads((docs / "data.json").read_text(encoding="utf-8"))
    assert data["summary"]["symbol_count"] == payload["summary"]["symbol_count"]
