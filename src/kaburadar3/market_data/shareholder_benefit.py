"""株主優待情報（みんかぶ / 株探）."""

from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_TIMEOUT = 15

_MINKABU_META = re.compile(
    r"株主優待は『(?P<kind>[^』]+)』.*?権利確定月は(?P<month>\d+)月"
)
_MINKABU_META_DETAIL = re.compile(r"株主優待では(?P<kind>[^。]+)。")
_KABUTAN_META = re.compile(
    r"株主優待に「(?P<kind>[^」]+)」を実施しています。"
    r"(?P<shares>\d+)株保有から優待がもらえます。"
    r"権利確定月は(?P<month>\d+)月"
)
_SHARES = re.compile(r"優待発生株数\s*(?P<shares>\d+)")
_MIN_SHARES = re.compile(r"(\d+)株以上")


def _get_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.text


def _parse_minkabu(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"})
    description = str(meta.get("content", "")).strip() if meta else ""

    out: dict[str, Any] = {}
    match = _MINKABU_META.search(description)
    if match:
        out["kind"] = match.group("kind").strip()
        out["month"] = match.group("month")
    else:
        detail_match = _MINKABU_META_DETAIL.search(description)
        if detail_match:
            out["kind"] = detail_match.group("kind").strip()

    text = soup.get_text(" ", strip=True)
    shares_match = _SHARES.search(text)
    if shares_match:
        out["shares"] = shares_match.group("shares")

    if not out.get("kind"):
        for node in soup.select("[class*='yutai']"):
            node_text = node.get_text(" ", strip=True)
            if "優待発生株数" in node_text and "優待権利確定月" in node_text:
                kind = node_text.split("最低投資金額", 1)[0].strip()
                for token in ("食料品", "暮らし", "ポイントサービス", "教養・娯楽", "長期保有特典"):
                    if token in kind:
                        kind = kind.split(token, 1)[0].strip()
                if kind and len(kind) < 120:
                    out["kind"] = kind
                shares_match = _SHARES.search(node_text)
                if shares_match:
                    out["shares"] = shares_match.group("shares")
                month_match = re.search(r"優待権利確定月\s*(\d+)月", node_text)
                if month_match:
                    out["month"] = month_match.group(1)
                break

    if out.get("kind") and not out.get("month"):
        month_match = re.search(r"権利確定月は(\d+)月", description)
        if month_match:
            out["month"] = month_match.group(1)

    return out


def _parse_kabutan(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"})
    description = str(meta.get("content", "")).strip() if meta else ""

    match = _KABUTAN_META.search(description)
    if not match:
        return {}

    return {
        "kind": match.group("kind").strip(),
        "shares": match.group("shares"),
        "month": match.group("month"),
    }


def _format_benefit(data: dict[str, Any]) -> str:
    kind = str(data.get("kind", "")).strip()
    if not kind:
        return ""

    parts = [kind]
    shares = str(data.get("shares", "")).strip()
    month = str(data.get("month", "")).strip()
    if shares:
        parts.append(f"{shares}株以上")
    if month:
        parts.append(f"権利確定{month}月")
    return "。".join(parts) + "。"


def fetch_shareholder_benefit(code: str) -> str:
    """最新の株主優待概要。取得不可・優待なしは空文字または「なし」."""
    symbol = str(code).strip()
    if not symbol:
        return ""

    parsed: dict[str, Any] = {}
    try:
        parsed = _parse_minkabu(_get_html(f"https://minkabu.jp/stock/{symbol}/yutai"))
    except Exception:
        parsed = {}

    if not parsed.get("kind"):
        try:
            parsed = _parse_kabutan(_get_html(f"https://kabutan.jp/stock/yutai?code={symbol}"))
        except Exception:
            parsed = {}

    text = _format_benefit(parsed)
    if text:
        return text

    # 2670 など meta に制度名が無い銘柄は優待なし扱い
    return "なし"
