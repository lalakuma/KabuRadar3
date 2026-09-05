"""銘柄の配当・決算・バリュエーション（yfinance）."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable


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


def _load_yahoo_info(code: str) -> dict[str, Any]:
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
    return info if isinstance(info, dict) else {}


def _round_float(raw: Any, digits: int) -> float | None:
    if raw is None:
        return None
    try:
        return round(float(raw), digits)
    except (TypeError, ValueError):
        return None


def _pct(raw: Any, *, as_ratio: bool = True) -> float | None:
    value = _round_float(raw, 4)
    if value is None:
        return None
    if as_ratio and abs(value) <= 1:
        value *= 100
    return round(value, 2)


def _parse_dividend_from_info(info: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    annual = _round_float(info.get("dividendRate"), 0)
    if annual is not None:
        out["annual_yen"] = int(annual)

    yield_val = _pct(info.get("dividendYield"))
    if yield_val is not None:
        out["yield_pct"] = yield_val

    ex_date = _format_ex_date(info.get("exDividendDate"))
    if ex_date:
        out["ex_date"] = ex_date

    payout = _pct(info.get("payoutRatio"))
    if payout is not None:
        out["payout_ratio_pct"] = payout

    return out


def _parse_earnings_from_info(info: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    announcement = _format_ex_date(info.get("earningsTimestampStart")) or _format_ex_date(
        info.get("earningsTimestamp")
    )
    if announcement:
        out["announcement_date"] = announcement
        announcement_end = _format_ex_date(info.get("earningsTimestampEnd"))
        if announcement_end and announcement_end != announcement:
            out["announcement_date_end"] = announcement_end

    fiscal_end = _format_ex_date(info.get("nextFiscalYearEnd"))
    if fiscal_end:
        out["fiscal_year_end"] = fiscal_end
        try:
            out["fiscal_month"] = int(fiscal_end[5:7])
        except (TypeError, ValueError):
            pass

    if info.get("isEarningsDateEstimate") is True:
        out["is_estimate"] = True

    return out


def _parse_valuation_from_info(info: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    sector = str(info.get("sectorDisp") or info.get("sector") or "").strip()
    industry = str(info.get("industryDisp") or info.get("industry") or "").strip()
    if sector:
        out["sector"] = sector
    if industry:
        out["industry"] = industry

    for key, src, parser in (
        ("per", "trailingPE", lambda v: _round_float(v, 1)),
        ("forward_per", "forwardPE", lambda v: _round_float(v, 1)),
        ("pbr", "priceToBook", lambda v: _round_float(v, 2)),
        ("psr", "priceToSalesTrailing12Months", lambda v: _round_float(v, 2)),
        ("peg", "trailingPegRatio", lambda v: _round_float(v, 2)),
    ):
        parsed = parser(info.get(src))
        if parsed is not None:
            out[key] = parsed

    market_cap = info.get("marketCap")
    cap = _round_float(market_cap, 0)
    if cap is not None and cap > 0:
        out["market_cap_oku"] = int(round(cap / 1e8))

    current = _round_float(info.get("currentPrice") or info.get("regularMarketPrice"), 0)
    if current is not None:
        out["price_yen"] = int(current)

    target = _round_float(info.get("targetMeanPrice"), 0)
    if target is not None:
        out["target_price_yen"] = int(target)
        if current and current > 0:
            out["target_upside_pct"] = round((target / current - 1) * 100, 1)

    revenue_growth = _pct(info.get("revenueGrowth"))
    if revenue_growth is not None:
        out["revenue_growth_pct"] = revenue_growth

    earnings_growth = _pct(info.get("earningsGrowth"))
    if earnings_growth is not None:
        out["earnings_growth_pct"] = earnings_growth

    profit_margin = _pct(info.get("profitMargins"))
    if profit_margin is not None:
        out["profit_margin_pct"] = profit_margin

    roe = _pct(info.get("returnOnEquity"))
    if roe is not None:
        out["roe_pct"] = roe

    debt_to_equity = _round_float(info.get("debtToEquity"), 1)
    if debt_to_equity is not None:
        out["debt_to_equity"] = debt_to_equity

    return out


def fetch_fundamentals_snapshot(code: str) -> dict[str, Any]:
    """配当・決算・バリュエーションを1回の yfinance 取得で返す。"""
    info = _load_yahoo_info(code)
    if not info:
        return {}

    out: dict[str, Any] = {}
    dividend = _parse_dividend_from_info(info)
    if dividend:
        out["dividend"] = dividend
    earnings = _parse_earnings_from_info(info)
    if earnings:
        out["earnings"] = earnings
    valuation = _parse_valuation_from_info(info)
    if valuation:
        out["valuation"] = valuation
    return out


def fetch_dividend_info(code: str) -> dict[str, Any]:
    """配当情報を取得。失敗時は空 dict。"""
    return dict(fetch_fundamentals_snapshot(code).get("dividend") or {})


def fetch_earnings_info(code: str) -> dict[str, Any]:
    """決算期・次回決算発表予定日。失敗時は空 dict。"""
    return dict(fetch_fundamentals_snapshot(code).get("earnings") or {})


def fetch_valuation_info(code: str) -> dict[str, Any]:
    """PER/PBR 等のバリュエーション指標。失敗時は空 dict。"""
    return dict(fetch_fundamentals_snapshot(code).get("valuation") or {})
