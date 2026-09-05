from __future__ import annotations

from kaburadar3.qualitative.schema import QualityRating
from kaburadar3.qualitative.rater import _build_prompt, rate_symbol
from kaburadar3.news.fetch import fetch_news


def test_quality_rating_from_dict_clamps_stars() -> None:
    q = QualityRating.from_dict({"code": "9434", "stars": 9, "background": "test"})
    assert q.stars == 5


def test_quality_rating_accepts_fundamental_fields() -> None:
    q = QualityRating.from_dict(
        {
            "code": "2670",
            "stars": 4,
            "background": "背景",
            "material_analysis": "材料",
            "fundamental_summary": "本業堅調",
            "technical_view": "押し目",
            "trade_notes": "RSI60まで",
            "watch_points": ["決算", "地合い"],
            "valuation_view": "fair",
            "valuation": {"per": 18.4},
        }
    )
    assert q.material_analysis == "材料"
    assert q.fundamental_summary == "本業堅調"
    assert q.technical_view == "押し目"
    assert q.trade_notes == "RSI60まで"
    assert q.watch_points == ["決算", "地合い"]
    assert q.valuation_view == "fair"
    assert q.valuation["per"] == 18.4


def test_build_prompt_includes_fundamentals() -> None:
    prompt = _build_prompt(
        "2670",
        "エービーシー・マート",
        "新買",
        [],
        snapshot={
            "valuation": {"per": 18.4, "pbr": 2.1, "sector": "Consumer Cyclical"},
            "dividend": {"yield_pct": 2.9},
            "earnings": {"fiscal_month": 2, "announcement_date": "2026-10-07"},
        },
        benefit={"summary": "なし"},
        signal_ctx={"close": 2690, "rsi": 8.5, "rci": -75.2, "rci_turn": True},
    )
    assert "PER 18.4" in prompt
    assert "2月決算" in prompt
    assert "material_analysis" in prompt
    assert "technical_view" in prompt
    assert "trade_notes" in prompt
    assert "RSI4 8.50" in prompt
    assert "RSI60" in prompt
    assert "バックテスト" not in prompt


def test_rate_symbol_without_api_key(monkeypatch) -> None:
    monkeypatch.setattr("kaburadar3.qualitative.rater.fetch_news", lambda code, limit=5: [])
    monkeypatch.setattr(
        "kaburadar3.qualitative.rater.fetch_fundamentals_snapshot",
        lambda code: {"valuation": {"per": 10}},
    )
    monkeypatch.setattr(
        "kaburadar3.qualitative.rater.fetch_shareholder_benefit_detail",
        lambda code: {"summary": "なし"},
    )
    monkeypatch.setattr(
        "kaburadar3.qualitative.rater.generate_json",
        lambda prompt, model=None: (_ for _ in ()).throw(RuntimeError("GEMINI_API_KEY is not set")),
    )
    rating = rate_symbol("9434", name="ソフトバンク", use_cache=False)
    assert rating.stars == 3
    assert "AI評価不可" in rating.background
    assert rating.valuation.get("per") == 10


def test_fetch_news_returns_list() -> None:
    result = fetch_news("9434")
    assert isinstance(result, list)
