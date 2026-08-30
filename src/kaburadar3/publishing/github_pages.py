"""解析結果を GitHub Pages 用 docs/data.json に書き出す."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from kaburadar3.publishing.ci_meta import build_run_meta
from kaburadar3.settings.encoding import read_csv
from kaburadar3.settings.git_publish import resolve_publish_branch
from kaburadar3.settings.loader import read_path_config
from kaburadar3.settings import screening as conf
from kaburadar3.settings.paths import DOCS_DIR, PROJECT_ROOT
from kaburadar3.settings.runtime import actions_run_url, load_runtime_config, runtime_edit_url

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*_args, **_kwargs):  # type: ignore[no-redef]
        return False


def _ensure_env_loaded() -> None:
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        load_dotenv(env_file)


from kaburadar3.qualitative.rater import rate_signals
from kaburadar3.signals.daily_history import collect_daily_history
from kaburadar3.signals.special import apply_special_buy
from kaburadar3.signals.today import collect_today_signals

RESULTS_DIR = read_path_config("SHUUKEI", "PATH_HONBAN")
DATA_FILE = DOCS_DIR / "data.json"


def _find_summary_csv(directory: Path) -> Path | None:
    candidates = sorted(directory.glob("Y*_PF*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _parse_summary_filename(path: Path) -> dict:
    name = path.stem
    match = re.search(
        r"Y\d+_PF([\d.]+)_W(\d+)L(\d+)_rate([\d.]+)_all(\d+)",
        name,
    )
    if not match:
        return {}
    return {
        "pf": float(match.group(1)),
        "wins": int(match.group(2)),
        "losses": int(match.group(3)),
        "win_rate": float(match.group(4)),
        "total_income": int(match.group(5)),
    }


def _load_symbols(summary_csv: Path) -> list[dict]:
    df = read_csv(summary_csv)
    rows: list[dict] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "code": str(row.get("code", "")),
                "name": str(row.get("name", "")),
                "industry": str(row.get("sangyou", "")),
                "incomes": int(row.get("incomes", 0) or 0),
                "pf": float(row.get("pf", 0) or 0),
                "winlose": str(row.get("winlose", "")),
                "win_per": int(row.get("winPer", 0) or 0),
                "plus_gain": int(row.get("pg", 0) or 0),
                "minus_gain": int(row.get("mg", 0) or 0),
            }
        )
    rows.sort(key=lambda r: r["incomes"], reverse=True)
    return rows


def payload_without_timestamp(payload: dict) -> dict:
    """比較用: generated_at / run / controls を除いたペイロード。"""
    return {k: v for k, v in payload.items() if k not in ("generated_at", "run", "controls")}


def build_payload() -> dict:
    _ensure_env_loaded()
    if not RESULTS_DIR.is_dir():
        raise FileNotFoundError(f"結果フォルダがありません: {RESULTS_DIR}")

    summary_csv = _find_summary_csv(RESULTS_DIR)
    if summary_csv is None:
        raise FileNotFoundError(f"集計 CSV (Y*_PF*.csv) が見つかりません: {RESULTS_DIR}")

    symbols = _load_symbols(summary_csv)
    name_map = {s["code"]: s["name"] for s in symbols}
    runtime = load_runtime_config()
    today = collect_today_signals(RESULTS_DIR, name_map)
    daily = collect_daily_history(RESULTS_DIR, name_map)
    special, _state, special_lines = apply_special_buy(
        today.get("trade_date"),
        int(today.get("new_buy_count", 0)),
        runtime,
    )

    symbol_map = {s["code"]: s for s in symbols}
    signal_items = list(today.get("new_buy", [])) + list(today.get("sellback", []))
    quality = rate_signals(
        signal_items,
        symbol_map=symbol_map,
        trade_date=today.get("trade_date"),
        enabled=runtime.gemini_rating_enabled and bool(os.getenv("GEMINI_API_KEY", "").strip()),
        model=runtime.gemini_rating_model,
    )
    for key in ("new_buy", "sellback"):
        for item in today.get(key, []):
            code = str(item.get("code", ""))
            if code in quality:
                item["quality"] = quality[code]
            item["rsi_ok"] = item.get("rsi") is not None and item.get("rsi", 99) <= 10
            item["rci_ok"] = item.get("rci_turn") is True

    meta = _parse_summary_filename(summary_csv)
    wins = sum(1 for s in symbols if "W1" in s["winlose"] or "W2" in s["winlose"])
    losses = sum(1 for s in symbols if "L1" in s["winlose"])
    neutral = sum(1 for s in symbols if s["winlose"] == "W0L0")

    payload: dict = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "mode": conf.config_stance(),
        "summary": {
            "pf": meta.get("pf"),
            "wins": meta.get("wins", wins),
            "losses": meta.get("losses", losses),
            "win_rate": meta.get("win_rate"),
            "total_income": meta.get("total_income", sum(s["incomes"] for s in symbols)),
            "symbol_count": len(symbols),
            "neutral_count": neutral,
            "source_file": summary_csv.name,
        },
        "symbols": symbols,
        "today": today,
        "daily": daily,
        "special": special,
        "quality": quality,
        "runtime": runtime.raw,
        "controls": {
            "actions_run_url": actions_run_url(),
            "runtime_edit_url": runtime_edit_url(),
        },
        "line_events": special_lines,
    }
    run_meta = build_run_meta()
    if run_meta:
        payload["run"] = run_meta
    return payload


def _should_refresh_timestamp() -> bool:
    """CI 実行時は集計が同じでも更新日時を書き換える。"""
    return os.getenv("KABURADAR_REFRESH_TIMESTAMP", "").strip().lower() in ("1", "true", "yes")


def publish() -> dict:
    payload = build_payload()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    new_text = json.dumps(payload, ensure_ascii=False, indent=2)

    if DATA_FILE.exists() and not _should_refresh_timestamp():
        try:
            existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            old_stable = json.dumps(payload_without_timestamp(existing), ensure_ascii=False, indent=2)
            new_stable = json.dumps(payload_without_timestamp(payload), ensure_ascii=False, indent=2)
            if old_stable == new_stable:
                print("データに変更なし: docs/data.json は更新しません。")
                return existing
        except (json.JSONDecodeError, OSError):
            pass

    DATA_FILE.write_text(new_text, encoding="utf-8")
    print(f"Published: {DATA_FILE}")
    print(f"  symbols: {payload['summary']['symbol_count']}")
    print(f"  win_rate: {payload['summary'].get('win_rate')}%")
    return payload


def push_to_github(payload: dict) -> int:
    def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    add = _run_git(["add", "docs/data.json"])
    if add.returncode != 0:
        print(add.stderr or add.stdout)
        return add.returncode

    diff = _run_git(["diff", "--cached", "--quiet", "docs/data.json"])
    if diff.returncode == 0:
        print("変更なし: push をスキップしました。")
        return 0

    win_rate = payload["summary"].get("win_rate")
    income = payload["summary"].get("total_income")
    msg = f"解析結果を更新 (勝率 {win_rate}%, 損益 {income})"
    commit = _run_git(["commit", "-m", msg])
    if commit.returncode != 0:
        print(commit.stderr or commit.stdout)
        return commit.returncode

    branch = resolve_publish_branch()
    push = _run_git(["push", "origin", branch])
    if push.returncode != 0:
        print(push.stderr or push.stdout)
        return push.returncode

    print(f"GitHub へ push 完了 (origin/{branch})。1〜2分後に Pages が更新されます。")
    print("https://lalakuma.github.io/KabuRadar3/")
    return 0
