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
    dividend: dict[str, Any] = field(default_factory=dict)
    shareholder_benefit: str = ""
    shareholder_benefit_detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "code": self.code,
            "stars": self.stars,
            "background": self.background,
            "risk_factors": list(self.risk_factors),
            "confidence": self.confidence,
            "sources": list(self.sources),
        }
        if self.dividend:
            out["dividend"] = dict(self.dividend)
        if self.shareholder_benefit:
            out["shareholder_benefit"] = self.shareholder_benefit
        if self.shareholder_benefit_detail:
            out["shareholder_benefit_detail"] = dict(self.shareholder_benefit_detail)
        return out

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
        dividend = data.get("dividend") or {}
        if not isinstance(dividend, dict):
            dividend = {}
        benefit_detail = data.get("shareholder_benefit_detail") or {}
        if not isinstance(benefit_detail, dict):
            benefit_detail = {}
        return cls(
            code=str(data.get("code", "")),
            stars=stars,
            background=str(data.get("background", "")).strip() or "情報不足",
            risk_factors=[str(x) for x in risks][:5],
            confidence=str(data.get("confidence", "medium")),
            sources=[str(x) for x in sources][:5],
            dividend=dividend,
            shareholder_benefit=str(data.get("shareholder_benefit", "")).strip(),
            shareholder_benefit_detail=benefit_detail,
        )
