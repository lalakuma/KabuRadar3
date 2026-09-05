"""Gemini による銘柄質 ★1-5 評価."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kaburadar3.market_data.fundamentals import fetch_fundamentals_snapshot
from kaburadar3.market_data.shareholder_benefit import fetch_shareholder_benefit_detail
from kaburadar3.news.fetch import NewsItem, fetch_news
from kaburadar3.qualitative.gemini_client import generate_json
from kaburadar3.qualitative.rating_history import append_signal_ratings
from kaburadar3.qualitative.schema import QualityRating
from kaburadar3.settings.paths import PROJECT_ROOT

CACHE_FILE = PROJECT_ROOT / "data" / "quality_cache.json"
PROMPT_VERSION = 3


def _cache_key(code: str, trade_date: str) -> str:
    return f"v{PROMPT_VERSION}:{trade_date}:{code}"


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
    if dividend.get("payout_ratio_pct") is not None:
        parts.append(f"配当性向 {dividend['payout_ratio_pct']}%")
    return " · ".join(parts) if parts else "（配当データなし）"


def _format_earnings_hint(earnings: dict[str, Any]) -> str:
    if not earnings:
        return "（決算データなし）"
    parts: list[str] = []
    if earnings.get("fiscal_month") is not None:
        parts.append(f"{earnings['fiscal_month']}月決算")
    if earnings.get("announcement_date"):
        label = f"次回決算発表 {earnings['announcement_date']}"
        if earnings.get("is_estimate"):
            label += "（予想）"
        parts.append(label)
    return " · ".join(parts) if parts else "（決算データなし）"


def _format_valuation_hint(valuation: dict[str, Any]) -> str:
    if not valuation:
        return "（バリュエーションデータなし）"
    parts: list[str] = []
    if valuation.get("sector"):
        label = str(valuation["sector"])
        if valuation.get("industry"):
            label += f" / {valuation['industry']}"
        parts.append(label)
    if valuation.get("market_cap_oku") is not None:
        parts.append(f"時価総額 約{valuation['market_cap_oku']}億円")
    if valuation.get("per") is not None:
        parts.append(f"PER {valuation['per']}")
    if valuation.get("forward_per") is not None:
        parts.append(f"予想PER {valuation['forward_per']}")
    if valuation.get("pbr") is not None:
        parts.append(f"PBR {valuation['pbr']}")
    if valuation.get("revenue_growth_pct") is not None:
        parts.append(f"売上成長 {valuation['revenue_growth_pct']}%")
    if valuation.get("earnings_growth_pct") is not None:
        parts.append(f"利益成長 {valuation['earnings_growth_pct']}%")
    if valuation.get("profit_margin_pct") is not None:
        parts.append(f"利益率 {valuation['profit_margin_pct']}%")
    if valuation.get("roe_pct") is not None:
        parts.append(f"ROE {valuation['roe_pct']}%")
    if valuation.get("target_price_yen") is not None:
        upside = valuation.get("target_upside_pct")
        upside_text = f"（+{upside}%）" if isinstance(upside, (int, float)) and upside > 0 else ""
        if isinstance(upside, (int, float)) and upside < 0:
            upside_text = f"（{upside}%）"
        parts.append(f"アナリスト目標 {valuation['target_price_yen']}円{upside_text}")
    return " · ".join(parts) if parts else "（バリュエーションデータなし）"


def _format_benefit_hint(benefit: dict[str, Any]) -> str:
    summary = str(benefit.get("summary") or "").strip()
    if not summary:
        return "（株主優待なし / データなし）"
    programs = benefit.get("programs") or []
    if not programs:
        return summary
    tier_lines: list[str] = []
    for program in programs[:2]:
        tiers = program.get("tiers") or []
        if not tiers:
            continue
        tier = tiers[0]
        tier_lines.append(f"{tier.get('shares', '')}: {tier.get('content', '')}")
    if tier_lines:
        return f"{summary} / {' · '.join(tier_lines)}"
    return summary


def _format_technical_hint(signal_ctx: dict[str, Any]) -> str:
    if not signal_ctx:
        return "（テクニカル数値なし）"
    parts: list[str] = []
    close = signal_ctx.get("close")
    if close is not None:
        parts.append(f"終値 {int(close):,}円")
    rsi = signal_ctx.get("rsi")
    if rsi is not None:
        parts.append(f"RSI4 {float(rsi):.2f}")
    rci = signal_ctx.get("rci")
    if rci is not None:
        parts.append(f"RCI {float(rci):.1f}")
    if signal_ctx.get("rci_turn"):
        parts.append("RCI上向き")
    mark = str(signal_ctx.get("mark") or "").strip()
    if mark:
        parts.append(f"シグナル {mark}")
    return " · ".join(parts) if parts else "（テクニカル数値なし）"


def _attach_market_data(
    rating: QualityRating,
    snapshot: dict[str, Any],
    benefit: dict[str, Any],
) -> QualityRating:
    dividend = snapshot.get("dividend") or {}
    if dividend:
        rating.dividend = dict(dividend)
    earnings = snapshot.get("earnings") or {}
    if earnings:
        rating.earnings = dict(earnings)
    valuation = snapshot.get("valuation") or {}
    if valuation:
        rating.valuation = dict(valuation)
    summary = str(benefit.get("summary") or "").strip()
    if summary:
        rating.shareholder_benefit = summary
        if benefit.get("programs"):
            rating.shareholder_benefit_detail = dict(benefit)
    return rating


def _apply_fundamentals(rating: QualityRating, code: str) -> QualityRating:
    snapshot = fetch_fundamentals_snapshot(code)
    benefit = fetch_shareholder_benefit_detail(code)
    return _attach_market_data(rating, snapshot, benefit)


def _build_prompt(
    code: str,
    name: str,
    signal: str,
    news: list[NewsItem],
    snapshot: dict[str, Any],
    benefit: dict[str, Any],
    signal_ctx: dict[str, Any] | None = None,
) -> str:
    news_lines = "\n".join(
        f"- [{n.published}] {n.title} ({n.publisher}) {n.url}".strip() for n in news
    ) or "- （直近ニュースなし）"
    dividend = snapshot.get("dividend") or {}
    earnings = snapshot.get("earnings") or {}
    valuation = snapshot.get("valuation") or {}
    signal_ctx = signal_ctx or {}
    return f"""あなたは日本株の短期トレード向けアナリストです。
テクニカル押し目シグナルに対し、材料・ファンダ・テクニカルを統合して短期反発の質を ★1〜★5 で評価してください。
各テキスト項目は具体的に、読み手が投資判断できるよう **十分な分量** で書いてください（短い1文だけにしない）。

## 銘柄
- コード: {code}
- 名称: {name or '不明'}
- 当日シグナル: {signal}

## テクニカル（当日）
- {_format_technical_hint(signal_ctx)}

## ファンダメンタル（参考データ）
- バリュエーション: {_format_valuation_hint(valuation)}
- 配当: {_format_dividend_hint(dividend)}
- 決算: {_format_earnings_hint(earnings)}
- 株主優待: {_format_benefit_hint(benefit)}

## 直近ニュース
{news_lines}

## トレード前提（このツールのルール）
- エントリー: RSI4 極端な押し目 + RCI 反転など
- 利確: RSI4 が 60 超まで基本ホールド（-3% は保険損切り）
- 最大保有: 約100営業日

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

## 判定の注意
- 参考データの PER/PBR/成長率/決算日/優待を必ず踏まえ、業績とバリュエーションの両面から判断する。
- 決算発表が近い（2週間以内）場合は risk_factors と watch_points に決算関連を入れる。
- 増収増益・本業堅調が確認でき、下落が決算後利確・材料出尽くし・コンセンサス想定線・粗利率への一時的警戒などなら、★3 ではなく ★4 を優先する。
- 通期最高益級のサプライズや明確な過剰売りなら ★5 を検討する。
- ニュース件数が少なくても、取得できた材料から ★4/★5 の条件に該当すれば積極的に付ける。情報不足だけで ★3 にしない。
- trade_notes では RSI60 利確ルールと決算・材料リスクを踏まえた短期の持ち方を書く。

## 出力（JSON のみ）
{{
  "code": "{code}",
  "stars": 1-5 の整数,
  "background": "なぜ今下落しているか。ニュースと地合いを踏まえ日本語2-4文",
  "material_analysis": "直近ニュース・材料の読み解き。好材料/悪材料/織り込み度を日本語3-5文",
  "fundamental_summary": "業績・財務・バリュエーション・決算時期・優待/配当を踏まえた分析を日本語4-6文",
  "technical_view": "RSI/RCI押し目シグナルの質。反発しやすい局面かを日本語2-3文",
  "trade_notes": "RSI60利確・損切り・決算前後など短期トレード上の留意点を日本語2-3文",
  "valuation_view": "cheap|fair|expensive|unknown",
  "risk_factors": ["リスク1", "リスク2", "リスク3"],
  "watch_points": ["今後確認すること1", "今後確認すること2"],
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
    signal_ctx: dict[str, Any] | None = None,
) -> QualityRating:
    del pf, win_rate  # 銘柄別バックテストはサンプル不足のためプロンプトから除外
    trade_date = trade_date or ""
    cache = cache if cache is not None else load_cache()
    key = _cache_key(code, trade_date) if trade_date else code
    snapshot = fetch_fundamentals_snapshot(code)
    benefit = fetch_shareholder_benefit_detail(code)
    signal_ctx = signal_ctx or {}

    if use_cache and key in cache:
        rating = _attach_market_data(QualityRating.from_dict(cache[key]), snapshot, benefit)
        if trade_date:
            cache[key] = rating.to_dict()
        return rating

    news = fetch_news(code, limit=8)
    prompt = _build_prompt(code, name, signal, news, snapshot, benefit, signal_ctx)
    try:
        raw = generate_json(prompt, model=model)
    except Exception as exc:
        raw = {
            "code": code,
            "stars": 3,
            "background": f"AI評価不可: {exc}",
            "material_analysis": "",
            "fundamental_summary": "",
            "technical_view": "",
            "trade_notes": "",
            "valuation_view": "unknown",
            "risk_factors": ["評価失敗"],
            "watch_points": [],
            "confidence": "low",
            "sources": [n.url for n in news if n.url][:3],
        }

    rating = _attach_market_data(QualityRating.from_dict(raw), snapshot, benefit)
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
            model=model,
            use_cache=True,
            cache=cache,
            signal_ctx={
                "close": item.get("close"),
                "rsi": item.get("rsi"),
                "rci": item.get("rci"),
                "rci_turn": item.get("rci_turn"),
                "mark": item.get("mark"),
            },
        )
        out[code] = rating.to_dict()

    if trade_date:
        save_cache(cache)
        append_signal_ratings(trade_date, signals, out, model=model)
    return out
