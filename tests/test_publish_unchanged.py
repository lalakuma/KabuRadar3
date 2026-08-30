from __future__ import annotations

import json

from kaburadar3.publishing import github_pages as pub


def test_payload_without_timestamp() -> None:
    payload = {"generated_at": "t1", "mode": "LO", "summary": {"pf": 1.0}, "symbols": []}
    stripped = pub.payload_without_timestamp(payload)
    assert "generated_at" not in stripped
    assert stripped["mode"] == "LO"


def test_publish_skips_when_only_timestamp_changes(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    data_file = docs / "data.json"
    monkeypatch.setattr(pub, "DOCS_DIR", docs)
    monkeypatch.setattr(pub, "DATA_FILE", data_file)

    payload = {
        "generated_at": "2020-01-01T00:00:00",
        "mode": "LO",
        "summary": {"symbol_count": 1, "win_rate": 50.0},
        "symbols": [{"code": "7203", "incomes": 100}],
    }
    data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(pub, "build_payload", lambda: {**payload, "generated_at": "2099-12-31T23:59:59"})
    result = pub.publish()

    assert result["generated_at"] == "2020-01-01T00:00:00"
    on_disk = json.loads(data_file.read_text(encoding="utf-8"))
    assert on_disk["generated_at"] == "2020-01-01T00:00:00"


def test_publish_refreshes_timestamp_when_forced(tmp_path, monkeypatch) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    data_file = docs / "data.json"
    monkeypatch.setattr(pub, "DOCS_DIR", docs)
    monkeypatch.setattr(pub, "DATA_FILE", data_file)
    monkeypatch.setenv("KABURADAR_REFRESH_TIMESTAMP", "1")

    payload = {
        "generated_at": "2020-01-01T00:00:00",
        "mode": "LO",
        "summary": {"symbol_count": 1, "win_rate": 50.0},
        "symbols": [{"code": "7203", "incomes": 100}],
    }
    data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(pub, "build_payload", lambda: {**payload, "generated_at": "2099-12-31T23:59:59"})
    result = pub.publish()

    assert result["generated_at"] == "2099-12-31T23:59:59"
    on_disk = json.loads(data_file.read_text(encoding="utf-8"))
    assert on_disk["generated_at"] == "2099-12-31T23:59:59"
