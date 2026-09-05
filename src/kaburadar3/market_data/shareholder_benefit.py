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
    r"株主優待は『(?P<kind>[^』]+)』(?:.*?優待利回りは(?P<yield>[^%]+)%)?"
    r".*?権利確定月は(?P<month>\d+)月"
)
_MINKABU_META_DETAIL = re.compile(r"株主優待では(?P<kind>[^。]+)。")
_KABUTAN_META = re.compile(
    r"株主優待に「(?P<kind>[^」]+)」を実施しています。"
    r"(?P<shares>\d+)株保有から優待がもらえます。"
    r"権利確定月は(?P<month>\d+)月"
)
_SHARES = re.compile(r"優待発生株数\s*(?P<shares>\d+)")
_SKIP_HEADING = ("ランキング", "おすすめ", "証券会社", "ニュース", "9月の")


def _get_html(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT)
    response.raise_for_status()
    return response.text


def _clean_note(text: str) -> str:
    note = re.sub(r"\s+", " ", text).strip()
    return note


def _table_title(table: BeautifulSoup) -> str:
    for tag in table.find_all_previous(["h2", "h3", "h4"], limit=8):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) > 80:
            continue
        if any(token in text for token in _SKIP_HEADING):
            continue
        return text
    return ""


def _parse_minkabu_tables(soup: BeautifulSoup) -> list[dict[str, Any]]:
    programs: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = rows[0].get_text(" ", strip=True)
        if "必要株数" not in header or "優待内容" not in header:
            continue

        tiers: list[dict[str, str]] = []
        for row in rows[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if not cells:
                continue
            shares = cells[0]
            if "株" not in shares:
                continue
            content = cells[1] if len(cells) > 1 else ""
            note = _clean_note(cells[2]) if len(cells) > 2 else ""
            if not content and not note:
                continue
            tiers.append({"shares": shares, "content": content, "note": note})

        if tiers:
            programs.append({"title": _table_title(table), "tiers": tiers})
    return programs


def _parse_minkabu(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"})
    description = str(meta.get("content", "")).strip() if meta else ""

    out: dict[str, Any] = {"source": "minkabu"}
    match = _MINKABU_META.search(description)
    if match:
        out["kind"] = match.group("kind").strip()
        out["month"] = match.group("month")
        yield_val = (match.group("yield") or "").strip()
        if yield_val and yield_val not in {"---", "—"}:
            out["yield_pct"] = yield_val
    else:
        detail_match = _MINKABU_META_DETAIL.search(description)
        if detail_match:
            out["kind"] = detail_match.group("kind").strip()

    text = soup.get_text(" ", strip=True)
    shares_match = _SHARES.search(text)
    if shares_match:
        out["min_shares"] = int(shares_match.group("shares"))

    if not out.get("kind"):
        for node in soup.select("[class*='yutai']"):
            node_text = node.get_text(" ", strip=True)
            if "優待発生株数" not in node_text or "優待権利確定月" not in node_text:
                continue
            kind = node_text.split("最低投資金額", 1)[0].strip()
            for token in ("食料品", "暮らし", "ポイントサービス", "教養・娯楽", "長期保有特典"):
                if token in kind:
                    kind = kind.split(token, 1)[0].strip()
            if kind and len(kind) < 120:
                out["kind"] = kind
            shares_match = _SHARES.search(node_text)
            if shares_match:
                out["min_shares"] = int(shares_match.group("shares"))
            month_match = re.search(r"優待権利確定月\s*(\d+)月", node_text)
            if month_match:
                out["month"] = month_match.group(1)
            break

    if out.get("kind") and not out.get("month"):
        month_match = re.search(r"権利確定月は(\d+)月", description)
        if month_match:
            out["month"] = month_match.group("month")

    programs = _parse_minkabu_tables(soup)
    if programs:
        out["programs"] = programs
        if not out.get("min_shares"):
            first = programs[0]["tiers"][0]["shares"]
            num_match = re.search(r"(\d+)", first)
            if num_match:
                out["min_shares"] = int(num_match.group(1))

    return out


def _parse_kabutan(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": "description"})
    description = str(meta.get("content", "")).strip() if meta else ""

    match = _KABUTAN_META.search(description)
    if not match:
        return {}

    shares = int(match.group("shares"))
    kind = match.group("kind").strip()
    return {
        "source": "kabutan",
        "kind": kind,
        "min_shares": shares,
        "month": match.group("month"),
        "programs": [
            {
                "title": kind,
                "tiers": [{"shares": f"{shares}株以上", "content": kind, "note": ""}],
            }
        ],
    }


def _format_summary(data: dict[str, Any]) -> str:
    kind = str(data.get("kind", "")).strip()
    if not kind:
        return ""

    parts = [kind]
    min_shares = data.get("min_shares")
    if min_shares:
        parts.append(f"{min_shares}株以上")
    month = data.get("month")
    if month:
        parts.append(f"権利確定{month}月")
    return "。".join(str(p) for p in parts) + "。"


def _format_benefit(data: dict[str, Any]) -> str:
    """詳細テキスト（キャッシュ・フォールバック用）."""
    summary = _format_summary(data)
    if not summary:
        return ""

    lines = [summary.rstrip("。")]
    programs = data.get("programs") or []
    for program in programs:
        title = str(program.get("title", "")).strip()
        if title and title not in summary:
            lines.append(f"【{title}】")
        for tier in program.get("tiers") or []:
            shares = tier.get("shares", "")
            content = tier.get("content", "")
            note = tier.get("note", "")
            line = f"・{shares}: {content}".strip()
            if note:
                line += f"（{note}）"
            lines.append(line)

    return "\n".join(lines)


def fetch_shareholder_benefit_detail(code: str) -> dict[str, Any]:
    """最新の株主優待詳細。優待なしは {"summary": "なし"}。"""
    symbol = str(code).strip()
    if not symbol:
        return {"summary": ""}

    parsed: dict[str, Any] = {}
    try:
        parsed = _parse_minkabu(_get_html(f"https://minkabu.jp/stock/{symbol}/yutai"))
    except Exception:
        parsed = {}

    if not parsed.get("kind") and not parsed.get("programs"):
        try:
            parsed = _parse_kabutan(_get_html(f"https://kabutan.jp/stock/yutai?code={symbol}"))
        except Exception:
            parsed = {}

    if not parsed.get("kind") and not parsed.get("programs"):
        return {"summary": "なし", "source": "none"}

    summary = _format_summary(parsed)
    parsed["summary"] = summary or "なし"
    parsed["text"] = _format_benefit(parsed)
    return parsed


def fetch_shareholder_benefit(code: str) -> str:
    """最新の株主優待概要（後方互換）."""
    detail = fetch_shareholder_benefit_detail(code)
    return str(detail.get("summary") or detail.get("text") or "")
