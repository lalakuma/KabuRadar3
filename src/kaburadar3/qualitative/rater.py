"""Gemini による銘柄質 ★1-5 評価."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kaburadar3.news.fetch import NewsItem, fetch_news
from kaburadar3.qualitative.gemini_client import generate_json
from kaburadar3.qualitative.schema import QualityRating
from kaburadar3.settings.paths import PROJECT_ROOT

CACHE_FILE = PROJECT_ROOT / "data" / "quality_cache.json"


def _cache_key(code: str, trade_date: str) -> str:
    return f"{trade_date}:{code}"


def load_cache(path: Path | None = None) -> dict[str, dict[str, Any]]:
    target = path or CACHE_FILE
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    target = path or CACHE_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_prompt(
    code: str,
    name: str,
    signal: str,
    news: list[NewsItem],
    pf: float | None = None,
    win_rate: float | None = None,
) -> str:
    news_lines = "\n".join(
        f"- [{n.published}] {n.title} ({n.publisher}) {n.url}".strip() for n in news
    ) or "- （直近ニュースなし）"
    stats = ""
    if pf is not None:
        stats += f"PF={pf} "
    if win_rate is not None:
        stats += f"勝率={win_rate}%"
    return f"""あなたは日本株の短期トレード向けアナリストです。
銘柄の「下落理由・背景」から短期反発の質を ★1〜★5 で評価してください。

## 銘柄
- コード: {code}
- 名称: {name or '不明'}
- 当日シグナル: {signal}
- バックテスト参考: {stats or 'なし'}

## 直近ニュース
{news_lines}

## 評価基準
- ★5: 一時的要因・需給要因が主で、ファンダは大きく毀損していない
- ★4: やや良い。反発余地が比較的大きい
- ★3: 中立・情報不足
- ★2: 構造的リスクや業績懸念が残る
- ★1: 継続的な悪材料・倒産/重大不祥事レベルの懸念

## 出力（JSON のみ）
{{
  "code": "{code}",
  "stars": 1-5 の整数,
  "background": "下落理由・背景を日本語1-2文",
  "risk_factors": ["リスク1", "リスク2"],
  "confidence": "high|medium|low",
  "sources": ["参照URL"]
}}
"""


def rate_symbol(
    code: str,
    name: str = "",
    signal: str = "新買",
    trade_date: str | None = None,
    pf: float | None = None,
    win_rate: float | None = None,
    model: str | None = None,
    use_cache: bool = True,
    cache: dict[str, dict[str, Any]] | None = None,
) -> QualityRating:
    trade_date = trade_date or ""
    cache = cache if cache is not None else load_cache()
    key = _cache_key(code, trade_date) if trade_date else code
    if use_cache and key in cache:
        return QualityRating.from_dict(cache[key])

    news = fetch_news(code)
    prompt = _build_prompt(code, name, signal, news, pf=pf, win_rate=win_rate)
    try:
        raw = generate_json(prompt, model=model)
    except Exception as exc:
        raw = {
            "code": code,
            "stars": 3,
            "background": f"AI評価不可: {exc}",
            "risk_factors": ["評価失敗"],
            "confidence": "low",
            "sources": [n.url for n in news if n.url][:3],
        }

    rating = QualityRating.from_dict(raw)
    if trade_date:
        cache[key] = rating.to_dict()
    return rating


def rate_signals(
    signals: list[dict[str, Any]],
    symbol_map: dict[str, dict[str, Any]] | None = None,
    trade_date: str | None = None,
    enabled: bool = True,
    model: str | None = None,
) -> dict[str, dict[str, Any]]:
    """シグナル銘柄リストを評価し code -> rating dict を返す。"""
    if not enabled:
        return {}

    symbol_map = symbol_map or {}
    cache = load_cache()
    out: dict[str, dict[str, Any]] = {}

    for item in signals:
        code = str(item.get("code", "")).strip()
        if not code:
            continue
        sym = symbol_map.get(code, {})
        rating = rate_symbol(
            code=code,
            name=str(item.get("name") or sym.get("name") or ""),
            signal=str(item.get("mark") or "新買"),
            trade_date=trade_date,
            pf=sym.get("pf"),
            win_rate=sym.get("win_per"),
            model=model,
            use_cache=True,
            cache=cache,
        )
        out[code] = rating.to_dict()

    if trade_date:
        save_cache(cache)
    return out
