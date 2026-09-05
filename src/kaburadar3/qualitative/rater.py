"""Gemini による銘柄質 ★1-5 評価."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kaburadar3.market_data.fundamentals import fetch_dividend_info
from kaburadar3.market_data.shareholder_benefit import fetch_shareholder_benefit_detail
from kaburadar3.news.fetch import NewsItem, fetch_news
from kaburadar3.qualitative.gemini_client import generate_json
from kaburadar3.qualitative.rating_history import append_signal_ratings
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


def _format_dividend_hint(dividend: dict[str, Any]) -> str:
    if not dividend:
        return "（配当データなし）"
    parts: list[str] = []
    if dividend.get("yield_pct") is not None:
        parts.append(f"利回り {dividend['yield_pct']}%")
    if dividend.get("annual_yen") is not None:
        parts.append(f"年間 {dividend['annual_yen']}円/株")
    if dividend.get("ex_date"):
        parts.append(f"権利付き最終日 {dividend['ex_date']}")
    return " · ".join(parts) if parts else "（配当データなし）"


def _apply_fundamentals(rating: QualityRating, code: str) -> QualityRating:
    dividend = fetch_dividend_info(code)
    if dividend:
        rating.dividend = dividend
    benefit = fetch_shareholder_benefit_detail(code)
    summary = str(benefit.get("summary") or "").strip()
    if summary:
        rating.shareholder_benefit = summary
        if benefit.get("programs"):
            rating.shareholder_benefit_detail = benefit
    return rating


def _build_prompt(
    code: str,
    name: str,
    signal: str,
    news: list[NewsItem],
    pf: float | None = None,
    win_rate: float | None = None,
    dividend: dict[str, Any] | None = None,
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
- 配当（参考）: {_format_dividend_hint(dividend or {})}

## 直近ニュース
{news_lines}

## 評価基準（★1〜★5）

★5（超本命）:
- 通期最高益や大幅増益など業績は絶好調。
- 下落理由が「コンセンサス微未達」「過剰な連れ安」「大手証券の目標株価引き下げ」など、一時的な過剰売り（絶好の押し目）である場合。
- または「悪材料後の大出来高アク抜け」「大規模自社株買い同時発表」「親会社・グループ都合の過剰連れ安」に該当する場合。

★4（優良・主戦場）:
- 本業の業績は堅調。
- 進捗遅れや決算直後の利確売り、全体地合いによる連れ安など一時的な下落で、企業価値は健全な場合。

★3（中立・様子見）:
- 下落理由が明確でない、または好悪材料が拮抗している場合。

★2（警戒・スルー推奨）:
- 業績悪化の兆候がある、または下落圧力が長引く可能性が高い場合。

★1（危険・絶対見送り）:
- 「公募増資・新株発行（希薄化）」「通期業績の下方修正」「赤字転落」「減配」「不正・不祥事」など、企業価値そのものを損なう構造的悪材料。

上記基準に最も近い星を1つ選び、該当理由を background に簡潔に書いてください。

## 判定の注意
- 増収増益・本業堅調が確認でき、下落が決算後利確・材料出尽くし・コンセンサス想定線・粗利率への一時的警戒などなら、★3 ではなく ★4 を優先する。
- 通期最高益級のサプライズや明確な過剰売りなら ★5 を検討する。
- ニュース件数が少なくても、取得できた材料から ★4/★5 の条件に該当すれば積極的に付ける。情報不足だけで ★3 にしない。

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
        rating = _apply_fundamentals(QualityRating.from_dict(cache[key]), code)
        if trade_date:
            cache[key] = rating.to_dict()
        return rating

    dividend = fetch_dividend_info(code)
    news = fetch_news(code)
    prompt = _build_prompt(
        code, name, signal, news, pf=pf, win_rate=win_rate, dividend=dividend
    )
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

    rating = _apply_fundamentals(QualityRating.from_dict(raw), code)
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
        append_signal_ratings(trade_date, signals, out, model=model)
    return out
