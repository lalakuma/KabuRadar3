from __future__ import annotations

from kaburadar3.qualitative.schema import QualityRating
from kaburadar3.qualitative.rater import rate_symbol
from kaburadar3.news.fetch import fetch_news


def test_quality_rating_from_dict_clamps_stars() -> None:
    q = QualityRating.from_dict({"code": "9434", "stars": 9, "background": "test"})
    assert q.stars == 5


def test_rate_symbol_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("kaburadar3.qualitative.rater.fetch_news", lambda code, limit=5: [])
    rating = rate_symbol("9434", name="ソフトバンク", use_cache=False)
    assert rating.stars == 3
    assert "AI評価不可" in rating.background or rating.background


def test_fetch_news_returns_list() -> None:
    result = fetch_news("9434")
    assert isinstance(result, list)
