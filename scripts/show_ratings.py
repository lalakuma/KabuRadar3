#!/usr/bin/env python3
"""docs/data.json の ★評価を一覧表示."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data.json"


def _clip(text: str, n: int = 100) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def _print_row(r: dict, prefix: str = "  ") -> None:
    q = r.get("quality") or {}
    stars = q.get("stars", "-")
    code = r.get("code", "")
    name = r.get("name", "")
    close = r.get("close")
    close_s = f" ¥{close:,}" if close is not None else ""
    print(f"{prefix}★{stars} {code} {name}{close_s}")
    for label, key in (
        ("背景", "background"),
        ("材料", "material_analysis"),
        ("ファンダ", "fundamental_summary"),
        ("シグナル", "technical_view"),
        ("トレード", "trade_notes"),
    ):
        val = _clip(str(q.get(key) or ""), 140)
        if val:
            print(f"{prefix}  {label}: {val}")
    risks = q.get("risk_factors") or []
    if risks:
        print(f"{prefix}  リスク: {' / '.join(str(x) for x in risks[:3])}")
    conf = q.get("confidence")
    vv = q.get("valuation_view")
    extras = [x for x in (f"信頼度={conf}" if conf else "", f"評価={vv}" if vv else "") if x]
    if extras:
        print(f"{prefix}  ({', '.join(extras)})")


def main() -> int:
    if not DATA.is_file():
        print(f"not found: {DATA}", file=sys.stderr)
        return 1
    data = json.loads(DATA.read_text(encoding="utf-8"))
    today = data.get("today") or {}
    trade_date = today.get("trade_date", "?")
    print(f"=== 最新シグナル日: {trade_date} (generated {data.get('generated_at', '?')}) ===")

    for key, title in (("new_buy", "新買"), ("sellback", "返売り")):
        rows = today.get(key) or []
        if not rows:
            continue
        print(f"\n[{title}] {len(rows)}件")
        for r in rows:
            _print_row(r)

    daily = data.get("daily") or {}
    buy_days = daily.get("buy_days")
    if buy_days is None:
        buy_days = [d for d in (daily.get("days") or []) if (d.get("new_buy_count") or 0) > 0]

    if buy_days:
        print("\n=== 直近の買いシグナル（日別） ===")
        for day in buy_days[:6]:
            buys = day.get("new_buy") or []
            if not buys:
                continue
            print(f"\n{day.get('date')} ({len(buys)}件)")
            for r in buys:
                _print_row(r, prefix="  ")

    quality_top = data.get("quality") or {}
    if quality_top:
        print(f"\n=== quality 辞書 ({len(quality_top)}件) ===")
        for code, q in sorted(quality_top.items()):
            print(f"  ★{q.get('stars', '-')} {code}  {_clip(q.get('background', ''), 80)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
