#!/usr/bin/env python3
"""指定日の買いシグナルを v3 プロンプトで再評価し、cache と publish を更新."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from kaburadar3.publishing.github_pages import publish
from kaburadar3.qualitative.rater import _cache_key, load_cache, rate_symbol, save_cache
from kaburadar3.settings.encoding import read_csv
from kaburadar3.settings.loader import read_path_config
from kaburadar3.settings.runtime import load_runtime_config
from kaburadar3.signals.today import _parse_close, _row_trade_date
from kaburadar3.strategy import rci as tc_rci

RESULTS_DIR = Path(read_path_config("SHUUKEI", "PATH_HONBAN"))
_CODE_CSV = re.compile(r"^code(\d+)", re.IGNORECASE)
MARK_NEW_BUY = "新買"


def _find_code_csv(results_dir: Path, code: str) -> Path | None:
    for path in sorted(results_dir.glob(f"code{code}*.csv")):
        if _CODE_CSV.match(path.name):
            return path
    return None


def _signal_ctx_for_date(path: Path, trade_date: str) -> dict:
    df = read_csv(path)
    if df.empty:
        return {}
    if "close" in df.columns:
        df = tc_rci.attach_rci(df, period=9)
    target = pd.Timestamp(trade_date).normalize()
    ctx: dict = {}
    for idx, row in df.iterrows():
        dt = _row_trade_date(row, idx)
        if dt is None or dt.normalize() != target:
            continue
        if str(row.get("mark", "")).strip() != MARK_NEW_BUY:
            continue
        close = _parse_close(row)
        if close is not None:
            ctx["close"] = int(round(close))
        if pd.notna(row.get("RSI4")):
            ctx["rsi"] = round(float(row["RSI4"]), 2)
        elif pd.notna(row.get("RSI")):
            ctx["rsi"] = round(float(row["RSI"]), 2)
        if pd.notna(row.get("RCI9")):
            ctx["rci"] = round(float(row["RCI9"]), 1)
        pos = df.index.get_loc(idx)
        if isinstance(pos, slice):
            pos = pos.stop - 1
        if pos > 0 and "RCI9" in df.columns and pd.notna(row.get("RCI9")):
            prev = df.iloc[pos - 1].get("RCI9")
            if pd.notna(prev):
                ctx["rci_turn"] = float(row["RCI9"]) > float(prev)
        ctx["mark"] = MARK_NEW_BUY
        break
    return ctx


def _purge_cache_for_date(cache: dict, trade_date: str, code: str) -> None:
    suffixes = (f"{trade_date}:{code}", f":{trade_date}:{code}")
    for key in list(cache.keys()):
        if any(key.endswith(s) or key == f"{trade_date}:{code}" for s in suffixes):
            del cache[key]


def rerate_date(trade_date: str, *, do_publish: bool = True) -> list[dict]:
    runtime = load_runtime_config()
    if not runtime.gemini_rating_enabled:
        raise RuntimeError("runtime.json: gemini_rating.enabled が false です")

    data_path = ROOT / "docs" / "data.json"
    if not data_path.is_file():
        raise FileNotFoundError(data_path)
    data = json.loads(data_path.read_text(encoding="utf-8"))
    day = next((d for d in (data.get("daily") or {}).get("days") or [] if d.get("date") == trade_date), None)
    if not day:
        raise ValueError(f"daily に {trade_date} がありません")
    signals = day.get("new_buy") or []
    if not signals:
        raise ValueError(f"{trade_date} に new_buy がありません")

    cache = load_cache()
    results: list[dict] = []
    print(f"=== rerate {trade_date} ({len(signals)}件) ===")
    for item in signals:
        code = str(item.get("code", "")).strip()
        if not code:
            continue
        _purge_cache_for_date(cache, trade_date, code)
        csv_path = _find_code_csv(RESULTS_DIR, code)
        signal_ctx = _signal_ctx_for_date(csv_path, trade_date) if csv_path else {}
        if not signal_ctx and item.get("close") is not None:
            signal_ctx = {"close": item.get("close"), "mark": item.get("mark") or MARK_NEW_BUY}

        rating = rate_symbol(
            code=code,
            name=str(item.get("name") or ""),
            signal=str(item.get("mark") or MARK_NEW_BUY),
            trade_date=trade_date,
            use_cache=False,
            cache=cache,
            signal_ctx=signal_ctx,
            model=runtime.gemini_rating_model,
        )
        row = rating.to_dict()
        results.append({"code": code, "name": item.get("name"), "stars": rating.stars, "quality": row})
        print(f"★{rating.stars} {code} {item.get('name')}")
        if rating.fundamental_summary:
            print(f"  ファンダ: {rating.fundamental_summary[:120]}…")
        elif rating.background:
            print(f"  背景: {rating.background[:120]}…")

    save_cache(cache)
    print(f"cache saved ({len(results)} entries)")

    if do_publish:
        import os

        os.environ["KABURADAR_REFRESH_TIMESTAMP"] = "1"
        publish()
        print("docs/data.json updated")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="指定日の ★評価を再生成")
    parser.add_argument("date", help="trade_date (YYYY-MM-DD)")
    parser.add_argument("--no-publish", action="store_true", help="cache のみ更新")
    args = parser.parse_args(argv)
    try:
        rerate_date(args.date, do_publish=not args.no_publish)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
