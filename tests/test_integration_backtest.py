from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from kaburadar3.data import repository as db
from kaburadar3.strategy import engine as bktst
from kaburadar3.strategy.models import KabInf


@pytest.fixture
def patched_db(monkeypatch: pytest.MonkeyPatch, minimal_db_path: Path):
    def _connect():
        conn = sqlite3.connect(minimal_db_path, isolation_level=None)
        return conn, conn.cursor()

    monkeypatch.setattr(db, "connect_db", _connect)
    return minimal_db_path


def test_backtst_proc_minimal_db(patched_db) -> None:  # noqa: ARG001
    prm = KabInf(sell_period=3, past_period=-60, srsi_hi=70, srsi_low=30)
    conn, cursor = db.connect_db()
    try:
        result = bktst.backtst_proc("1000", None, prm, conn, cursor)
    finally:
        db.close_db(conn)

    assert result != -1
