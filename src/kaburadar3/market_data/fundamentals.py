"""銘柄の配当などファンダメンタルズ（yfinance）."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _yahoo_ticker(code: str) -> str:
    symbol = str(code).strip()
    if not symbol:
        return ""
    if symbol.endswith(".T"):
        return symbol
    return f"{symbol}.T"


def _format_ex_date(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, UTC).strftime("%Y-%m-%d")
        except (OSError, OverflowError, ValueError):
            return None
    text = str(raw).strip()
    return text[:10] if text else None


def fetch_dividend_info(code: str) -> dict[str, Any]:
    """配当情報を取得。失敗時は空 dict。"""
    symbol = _yahoo_ticker(code)
    if not symbol:
        return {}

    try:
        import yfinance as yf
    except ImportError:
        return {}

    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        return {}

    out: dict[str, Any] = {}
    rate = info.get("dividendRate")
    if rate is not None:
        try:
            out["annual_yen"] = round(float(rate))
        except (TypeError, ValueError):
            pass

    yield_val = info.get("dividendYield")
    if yield_val is not None:
        try:
            y = float(yield_val)
            out["yield_pct"] = round(y * 100, 2) if y < 1 else round(y, 2)
        except (TypeError, ValueError):
            pass

    ex_date = _format_ex_date(info.get("exDividendDate"))
    if ex_date:
        out["ex_date"] = ex_date

    payout = info.get("payoutRatio")
    if payout is not None:
        try:
            p = float(payout)
            out["payout_ratio_pct"] = round(p * 100, 1) if p <= 1 else round(p, 1)
        except (TypeError, ValueError):
            pass

    return out
