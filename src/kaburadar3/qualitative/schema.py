"""Gemini 銘柄評価の入出力スキーマ."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityRating:
    code: str
    stars: int
    background: str
    risk_factors: list[str] = field(default_factory=list)
    confidence: str = "medium"
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "stars": self.stars,
            "background": self.background,
            "risk_factors": list(self.risk_factors),
            "confidence": self.confidence,
            "sources": list(self.sources),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityRating:
        stars = int(data.get("stars", 3))
        stars = max(1, min(5, stars))
        risks = data.get("risk_factors") or []
        if not isinstance(risks, list):
            risks = [str(risks)]
        sources = data.get("sources") or []
        if not isinstance(sources, list):
            sources = [str(sources)]
        return cls(
            code=str(data.get("code", "")),
            stars=stars,
            background=str(data.get("background", "")).strip() or "情報不足",
            risk_factors=[str(x) for x in risks][:5],
            confidence=str(data.get("confidence", "medium")),
            sources=[str(x) for x in sources][:5],
        )
