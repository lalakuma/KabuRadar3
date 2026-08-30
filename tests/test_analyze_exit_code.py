from __future__ import annotations

from pathlib import Path

from kaburadar3.pipeline.analyze import (
    AnalyzeStats,
    EXIT_NO_OUTPUT,
    EXIT_NO_SUMMARY,
    EXIT_OK,
    backtest_failed,
    compute_exit_code,
)


def test_backtest_failed() -> None:
    assert backtest_failed(-1) is True
    assert backtest_failed((0, [])) is False
    assert backtest_failed(0) is False


def test_compute_exit_code_ok(tmp_path: Path) -> None:
    summary = tmp_path / "Y0_PF1.0_W1L0_rate50.0_all100.csv"
    summary.write_text("code", encoding="utf-8")
    stats = AnalyzeStats(enabled=5, written=3, skipped=2)
    assert compute_exit_code(stats, summary) == EXIT_OK


def test_compute_exit_code_no_enabled() -> None:
    stats = AnalyzeStats(enabled=0)
    assert compute_exit_code(stats, None) == EXIT_OK


def test_compute_exit_code_no_output() -> None:
    stats = AnalyzeStats(enabled=10, written=0, skipped=10)
    assert compute_exit_code(stats, Path("Y0_PF1.csv")) == EXIT_NO_OUTPUT


def test_compute_exit_code_no_summary(tmp_path: Path) -> None:
    stats = AnalyzeStats(enabled=3, written=2)
    assert compute_exit_code(stats, None) == EXIT_NO_SUMMARY
    missing = tmp_path / "missing.csv"
    assert compute_exit_code(stats, missing) == EXIT_NO_SUMMARY
