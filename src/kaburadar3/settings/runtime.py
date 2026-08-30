"""運用設定 runtime.json の読み込み."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from kaburadar3.settings.paths import CONFIG_DIR, PROJECT_ROOT

RUNTIME_FILE = CONFIG_DIR / "runtime.json"

DEFAULT_RUNTIME: dict = {
    "special_buy": {
        "enabled": True,
        "min_new_buy_count": 7,
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
    special_buy_enabled: bool = True
    min_new_buy_count: int = 7
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
        sb = data.get("special_buy") or {}
        nt = data.get("notify") or {}
        gr = data.get("gemini_rating") or {}
        etf_codes = tuple(str(c) for c in sb.get("etf_codes", ["1321", "1306"]))
        return cls(
            special_buy_enabled=bool(sb.get("enabled", True)),
            min_new_buy_count=int(sb.get("min_new_buy_count", 7)),
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
            for key in ("special_buy", "notify", "gemini_rating"):
                if key in loaded and isinstance(loaded[key], dict):
                    merged[key].update(loaded[key])
    return RuntimeConfig.from_dict(merged)


def runtime_edit_url() -> str:
    repo = "lalakuma/KabuRadar3"
    return f"https://github.com/{repo}/edit/master/config/runtime.json"


def actions_run_url() -> str:
    repo = "lalakuma/KabuRadar3"
    return f"https://github.com/{repo}/actions/workflows/daily-screening.yml"
