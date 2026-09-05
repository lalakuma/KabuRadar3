"""Web 掲載の株主優待とみんかぶ/株探の最新情報を照合."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from kaburadar3.market_data.shareholder_benefit import (  # noqa: E402
    _parse_kabutan,
    _parse_minkabu,
    fetch_shareholder_benefit,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_sources(code: str) -> dict:
    out: dict = {}
    try:
        html = requests.get(
            f"https://minkabu.jp/stock/{code}/yutai", headers=HEADERS, timeout=15
        ).text
        out["minkabu"] = _parse_minkabu(html)
        meta = BeautifulSoup(html, "html.parser").find("meta", attrs={"name": "description"})
        out["minkabu_meta"] = (meta.get("content", "")[:200] if meta else "")
    except Exception as exc:  # noqa: BLE001
        out["minkabu"] = {"error": str(exc)}
    try:
        html = requests.get(
            f"https://kabutan.jp/stock/yutai?code={code}", headers=HEADERS, timeout=15
        ).text
        out["kabutan"] = _parse_kabutan(html)
        meta = BeautifulSoup(html, "html.parser").find("meta", attrs={"name": "description"})
        out["kabutan_meta"] = (meta.get("content", "")[:200] if meta else "")
    except Exception as exc:  # noqa: BLE001
        out["kabutan"] = {"error": str(exc)}
    return out


def main() -> int:
    data = json.loads((PROJECT_ROOT / "docs" / "data.json").read_text(encoding="utf-8"))
    rows: dict[str, dict] = {}
    for day in data.get("daily", {}).get("buy_days", []):
        for row in day.get("new_buy", []):
            q = row.get("quality") or {}
            benefit = (q.get("shareholder_benefit") or "").strip()
            if not benefit:
                continue
            rows[row["code"]] = {
                "name": row.get("name", ""),
                "date": day.get("date", ""),
                "web": benefit,
            }

    print("=== 優待照合（Web vs みんかぶ/株探 最新取得）===")
    ok = 0
    ng = 0
    for code in sorted(rows, key=lambda c: rows[c]["date"], reverse=True):
        info = rows[code]
        live = fetch_shareholder_benefit(code)
        match = live == info["web"]
        print(f"\n[{info['date']}] {code} {info['name']}")
        print(f"  Web   : {info['web']}")
        print(f"  Live  : {live}")
        print(f"  Match : {'OK' if match else 'NG'}")
        if not match:
            src = fetch_sources(code)
            print(f"  Minkabu parsed: {src.get('minkabu')}")
            print(f"  Kabutan parsed: {src.get('kabutan')}")
            if src.get("minkabu_meta"):
                print(f"  Minkabu meta  : {src['minkabu_meta']}")
            ng += 1
        else:
            ok += 1

    print(f"\n--- 結果: OK {ok} / NG {ng} / 計 {ok + ng} ---")
    return 0 if ng == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
