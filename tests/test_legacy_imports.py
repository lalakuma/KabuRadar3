from __future__ import annotations


def test_analysis_package_imports() -> None:
    from kaburadar3.analysis import backtest_proc
    from kaburadar3.analysis.indicators import rsi

    assert backtest_proc.Judge is not None
    assert callable(rsi.rsi_tradingview)


def test_cli_entrypoints_import() -> None:
    from kaburadar3.cli import analyze, publish, screening

    assert callable(analyze.main)
    assert callable(publish.main)
    assert callable(screening.main)
