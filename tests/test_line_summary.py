from __future__ import annotations

from pathlib import Path

from kaburadar3.notifications.summary import format_summary_header


def test_format_summary_header_parses_pf(tmp_path: Path) -> None:
    csv = tmp_path / "Y0_PF2.500_W10L5_rate66.67_all10000.csv"
    csv.write_text("code,name,incomes,pf,winlose,winPer,pg,mg\n", encoding="utf-8")
    text = format_summary_header(tmp_path)
    assert "PF 2.500" in text
    assert "66.7%" in text
    assert "10勝5敗" in text
