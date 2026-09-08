from __future__ import annotations

from pathlib import Path

import pytest

from kaburadar3.settings.runtime import RuntimeConfig
from kaburadar3.signals.special import (
    ROUTING_ETF,
    ROUTING_STOCKS,
    STATE_IDLE,
    STATE_SPECIAL_LONG,
    apply_special_buy,
    evaluate_routing,
)


def _runtime(**overrides) -> RuntimeConfig:
    base = {
        "special_buy": {
            "enabled": True,
            "min_new_buy_count": 8,
            "market_regime_min_pct": -15,
            "market_regime_lookback_days": 20,
            "etf_default": "1306",
            "etf_codes": ["1306"],
            "exit_rsi": 70,
        },
        "notify": {"special_buy_on": True, "special_exit": True},
    }
    sb = base["special_buy"]
    sb.update(overrides.get("special_buy", {}))
    return RuntimeConfig.from_dict(base)


def test_evaluate_routing_etf_when_count_and_market_ok() -> None:
    rt = _runtime()
    assert evaluate_routing(8, -10.0, rt) == ROUTING_ETF
    assert evaluate_routing(10, -15.0, rt) == ROUTING_ETF
    assert evaluate_routing(8, None, rt) == ROUTING_ETF


def test_evaluate_routing_stocks_when_market_deep() -> None:
    rt = _runtime()
    assert evaluate_routing(10, -18.0, rt) == ROUTING_STOCKS


def test_evaluate_routing_stocks_when_few_signals() -> None:
    rt = _runtime()
    assert evaluate_routing(7, -5.0, rt) == ROUTING_STOCKS


def test_apply_special_buy_etf_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rt = _runtime()
    state_path = tmp_path / "state.json"

    monkeypatch.setattr(
        "kaburadar3.signals.special._market_return_20d",
        lambda *a, **k: -8.0,
    )
    monkeypatch.setattr(
        "kaburadar3.signals.special._latest_rsi4",
        lambda *a, **k: (55.0, "2026-09-05"),
    )

    special, state, lines = apply_special_buy("2026-09-05", 9, rt, state_path=state_path)
    assert special["routing"] == ROUTING_ETF
    assert state["state"] == STATE_SPECIAL_LONG
    assert any("ETF推奨" in line for line in lines)


def test_apply_special_buy_stocks_on_deep_market(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rt = _runtime()
    state_path = tmp_path / "state.json"

    monkeypatch.setattr(
        "kaburadar3.signals.special._market_return_20d",
        lambda *a, **k: -20.0,
    )
    monkeypatch.setattr(
        "kaburadar3.signals.special._latest_rsi4",
        lambda *a, **k: (55.0, "2026-09-05"),
    )

    special, state, lines = apply_special_buy("2026-09-05", 12, rt, state_path=state_path)
    assert special["routing"] == ROUTING_STOCKS
    assert state["state"] == STATE_IDLE
    assert any("個別推奨" in line for line in lines)
