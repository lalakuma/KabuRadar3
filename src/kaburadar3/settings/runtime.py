"""運用設定 runtime.json の読み込み."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kaburadar3.settings.paths import CONFIG_DIR

RUNTIME_FILE = CONFIG_DIR / "runtime.json"

EXIT_PROFILE_PROFIT = "profit"
EXIT_PROFILE_WINRATE = "winrate"
EXIT_PROFILE_LABELS = {
    EXIT_PROFILE_PROFIT: "利益重視",
    EXIT_PROFILE_WINRATE: "勝率重視",
}

DEFAULT_RUNTIME: dict = {
    "exit_strategy": {
        "profile": EXIT_PROFILE_PROFIT,
    },
    "special_buy": {
        "enabled": True,
        "min_new_buy_count": 8,
        "market_regime_min_pct": -15.0,
        "market_regime_lookback_days": 20,
        "pick_method": "stars",
        "pick_count": 2,
        "pick_min_stars": 4,
        "etf_default": "1306",
        "etf_codes": ["1321", "1306"],
        "exit_rsi": 70,
    },
    "notify": {
        "today_buy": True,
        "today_sellback": True,
        "special_buy_on": True,
        "special_exit": True,
        "summary_top": False,
    },
    "gemini_rating": {
        "enabled": True,
        "model": "gemini-2.0-flash",
    },
}


@dataclass(frozen=True)
class RuntimeConfig:
    exit_profile: str = EXIT_PROFILE_PROFIT
    special_buy_enabled: bool = True
    min_new_buy_count: int = 8
    market_regime_min_pct: float = -15.0
    market_regime_lookback_days: int = 20
    pick_method: str = "stars"
    pick_count: int = 2
    pick_min_stars: int = 4
    etf_default: str = "1306"
    etf_codes: tuple[str, ...] = ("1321", "1306")
    exit_rsi: float = 70.0
    notify_today_buy: bool = True
    notify_today_sellback: bool = True
    notify_special_buy_on: bool = True
    notify_special_exit: bool = True
    notify_summary_top: bool = False
    gemini_rating_enabled: bool = True
    gemini_rating_model: str = "gemini-2.0-flash"
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> RuntimeConfig:
        es = data.get("exit_strategy") or {}
        sb = data.get("special_buy") or {}
        nt = data.get("notify") or {}
        gr = data.get("gemini_rating") or {}
        etf_codes = tuple(str(c) for c in sb.get("etf_codes", ["1321", "1306"]))
        profile = str(es.get("profile", EXIT_PROFILE_PROFIT)).strip().lower()
        if profile not in EXIT_PROFILE_LABELS:
            profile = EXIT_PROFILE_PROFIT
        return cls(
            exit_profile=profile,
            special_buy_enabled=bool(sb.get("enabled", True)),
            min_new_buy_count=int(sb.get("min_new_buy_count", 8)),
            market_regime_min_pct=float(sb.get("market_regime_min_pct", -15)),
            market_regime_lookback_days=int(sb.get("market_regime_lookback_days", 20)),
            pick_method=str(sb.get("pick_method", "stars")),
            pick_count=int(sb.get("pick_count", 2)),
            pick_min_stars=int(sb.get("pick_min_stars", 4)),
            etf_default=str(sb.get("etf_default", "1306")),
            etf_codes=etf_codes,
            exit_rsi=float(sb.get("exit_rsi", 70)),
            notify_today_buy=bool(nt.get("today_buy", True)),
            notify_today_sellback=bool(nt.get("today_sellback", True)),
            notify_special_buy_on=bool(nt.get("special_buy_on", True)),
            notify_special_exit=bool(nt.get("special_exit", True)),
            notify_summary_top=bool(nt.get("summary_top", False)),
            gemini_rating_enabled=bool(gr.get("enabled", True)),
            gemini_rating_model=str(gr.get("model", "gemini-2.0-flash")),
            raw=deepcopy(data),
        )


def load_runtime_config(path: Path | None = None) -> RuntimeConfig:
    target = path or RUNTIME_FILE
    merged = deepcopy(DEFAULT_RUNTIME)
    if target.is_file():
        loaded = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            for key in ("exit_strategy", "special_buy", "notify", "gemini_rating"):
                if key in loaded and isinstance(loaded[key], dict):
                    merged[key].update(loaded[key])
    return RuntimeConfig.from_dict(merged)


def apply_exit_profile_to_judge(jg: Any) -> None:
    """runtime.json の exit_strategy.profile で RSI60保持を切り替える."""
    profile = load_runtime_config().exit_profile
    if profile == EXIT_PROFILE_PROFIT:
        jg.rsi60_hold_rci_up = 1
    elif profile == EXIT_PROFILE_WINRATE:
        jg.rsi60_hold_rci_up = 0


def runtime_edit_url() -> str:
    repo = "lalakuma/KabuRadar3"
    return f"https://github.com/{repo}/edit/master/config/runtime.json"


def actions_run_url() -> str:
    repo = "lalakuma/KabuRadar3"
    return f"https://github.com/{repo}/actions/workflows/daily-screening.yml"
