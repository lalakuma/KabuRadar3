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
    material_analysis: str = ""
    fundamental_summary: str = ""
    technical_view: str = ""
    trade_notes: str = ""
    watch_points: list[str] = field(default_factory=list)
    valuation_view: str = ""
    dividend: dict[str, Any] = field(default_factory=dict)
    earnings: dict[str, Any] = field(default_factory=dict)
    valuation: dict[str, Any] = field(default_factory=dict)
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
        if self.material_analysis:
            out["material_analysis"] = self.material_analysis
        if self.fundamental_summary:
            out["fundamental_summary"] = self.fundamental_summary
        if self.technical_view:
            out["technical_view"] = self.technical_view
        if self.trade_notes:
            out["trade_notes"] = self.trade_notes
        if self.watch_points:
            out["watch_points"] = list(self.watch_points)
        if self.valuation_view:
            out["valuation_view"] = self.valuation_view
        if self.dividend:
            out["dividend"] = dict(self.dividend)
        if self.earnings:
            out["earnings"] = dict(self.earnings)
        if self.valuation:
            out["valuation"] = dict(self.valuation)
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
        watch_points = data.get("watch_points") or []
        if not isinstance(watch_points, list):
            watch_points = [str(watch_points)]
        sources = data.get("sources") or []
        if not isinstance(sources, list):
            sources = [str(sources)]
        dividend = data.get("dividend") or {}
        if not isinstance(dividend, dict):
            dividend = {}
        earnings = data.get("earnings") or {}
        if not isinstance(earnings, dict):
            earnings = {}
        valuation = data.get("valuation") or {}
        if not isinstance(valuation, dict):
            valuation = {}
        benefit_detail = data.get("shareholder_benefit_detail") or {}
        if not isinstance(benefit_detail, dict):
            benefit_detail = {}
        valuation_view = str(data.get("valuation_view", "")).strip().lower()
        if valuation_view not in {"cheap", "fair", "expensive", "unknown"}:
            valuation_view = ""
        return cls(
            code=str(data.get("code", "")),
            stars=stars,
            background=str(data.get("background", "")).strip() or "情報不足",
            risk_factors=[str(x) for x in risks][:5],
            confidence=str(data.get("confidence", "medium")),
            sources=[str(x) for x in sources][:5],
            material_analysis=str(data.get("material_analysis", "")).strip(),
            fundamental_summary=str(data.get("fundamental_summary", "")).strip(),
            technical_view=str(data.get("technical_view", "")).strip(),
            trade_notes=str(data.get("trade_notes", "")).strip(),
            watch_points=[str(x) for x in watch_points][:4],
            valuation_view=valuation_view,
            dividend=dividend,
            earnings=earnings,
            valuation=valuation,
            shareholder_benefit=str(data.get("shareholder_benefit", "")).strip(),
            shareholder_benefit_detail=benefit_detail,
        )
