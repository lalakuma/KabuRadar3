"""銘柄ニュース取得（yfinance）."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published: str
    publisher: str = ""


def _yahoo_ticker(code: str) -> str:
    code = str(code).strip()
    if code.endswith(".T"):
        return code
    return f"{code}.T"


def fetch_news(code: str, limit: int = 5) -> list[NewsItem]:
    """銘柄コードからニュース見出しを取得。失敗時は空リスト。"""
    try:
        import yfinance as yf
    except ImportError:
        return []

    try:
        ticker = yf.Ticker(_yahoo_ticker(code))
        raw = getattr(ticker, "news", None) or []
    except Exception:
        return []

    items: list[NewsItem] = []
    for row in raw[:limit]:
        if not isinstance(row, dict):
            continue
        content = row.get("content") if isinstance(row.get("content"), dict) else row
        title = str(content.get("title") or row.get("title") or "").strip()
        if not title:
            continue
        link = str(content.get("canonicalUrl") or content.get("clickThroughUrl") or row.get("link") or "")
        pub = content.get("pubDate") or row.get("providerPublishTime")
        if isinstance(pub, (int, float)):
            published = datetime.utcfromtimestamp(pub).strftime("%Y-%m-%d")
        else:
            published = str(pub or "")[:10]
        publisher = str(content.get("provider") or row.get("publisher") or "")
        items.append(NewsItem(title=title, url=link, published=published, publisher=publisher))
    return items
