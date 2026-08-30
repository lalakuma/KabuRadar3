from __future__ import annotations


def test_core_packages_import() -> None:
    from kaburadar3.data import repository
    from kaburadar3.pipeline import analyze, aggregate
    from kaburadar3.publishing import github_pages
    from kaburadar3.settings import screening
    from kaburadar3.strategy import engine, models, rsi, rci

    assert callable(repository.connect_db)
    assert callable(analyze.run)
    assert callable(aggregate.shuukei_toCsv)
    assert callable(github_pages.build_payload)
    assert callable(screening.get_config)
    assert callable(engine.backtst_proc)
    assert models.KabInf is not None
    assert callable(rsi.rsi_tradingview)
    assert callable(rci.jdg_rci_v_reversal)
