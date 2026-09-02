from __future__ import annotations

import os
from datetime import datetime
from typing import Iterable

import requests

from kaburadar3.settings.paths import PROJECT_ROOT

try:
    from dotenv import load_dotenv
except Exception:  # noqa: BLE001
    def load_dotenv(*_args, **_kwargs):  # type: ignore[no-redef]
        return False

_ENV_LOADED = False


def _get_env() -> tuple[str, list[str]]:
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv(PROJECT_ROOT / ".env")
        _ENV_LOADED = True
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    users = [x.strip() for x in os.getenv("LINE_USER_IDS", "").split(",") if x.strip()]
    return token, users


def is_configured() -> bool:
    token, users = _get_env()
    return bool(token and users and token != "change_me")


def is_weekend() -> bool:
    return datetime.today().isoweekday() in (6, 7)


def format_stars(stars: int | None) -> str:
    """★1〜5 を ★★★★☆ 形式の文字列にする。"""
    if stars is None:
        return ""
    value = max(1, min(5, int(stars)))
    return "★" * value + "☆" * (5 - value)


def format_signal_row(row: dict) -> str:
    """新買・返売り1行（コード・名称・終値・星）。"""
    close = row.get("close")
    yen = f" ¥{close:,d}" if close is not None else ""
    name = row.get("name") or ""
    quality = row.get("quality") or {}
    star_text = format_stars(quality.get("stars"))
    star_part = f" {star_text}" if star_text else ""
    return f"{row['code']} {name}{yen}{star_part}"


def notify(codes: Iterable[str], stance: str) -> bool:
    if is_weekend():
        return False

    token, users = _get_env()
    if not token or not users:
        raise RuntimeError("LINE settings are not configured in .env")

    message = "\n".join(codes) if codes else "not found"
    full_message = f"{stance} {message}".strip() if stance else message

    response = requests.post(
        "https://api.line.me/v2/bot/message/multicast",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"to": users, "messages": [{"type": "text", "text": full_message}]},
        timeout=15,
    )
    response.raise_for_status()
    return True


def notify_optional(codes: Iterable[str], stance: str) -> bool:
    """未設定・週末のときは例外にせずスキップする（個人運用向け）。"""
    if is_weekend():
        print("LINE: 週末のため送信しません。")
        return False
    if not is_configured():
        print("LINE: .env 未設定のため送信しません。")
        return False
    try:
        return notify(codes, stance)
    except Exception as exc:  # noqa: BLE001
        print(f"LINE: 送信失敗 ({exc})")
        return False


def notify_analysis_summary(stance: str | None = None, limit: int = 10) -> bool:
    """最新集計 CSV から上位銘柄を LINE 送信する。"""
    from datetime import datetime, timezone

    from kaburadar3.notifications.summary import format_summary_header, format_top_symbols
    from kaburadar3.publishing.ci_meta import pages_public_url, workflow_run_url
    from kaburadar3.settings import screening as conf

    if stance is None:
        stance = conf.config_stance()

    lines = format_top_symbols(limit=limit)
    if not lines:
        print("LINE: 集計 CSV がないため送信しません。")
        return False

    now = datetime.now(timezone.utc).astimezone()
    mode_label = "HI（RSI4反転）" if stance == "HI" else "LO"
    body: list[str] = [
        f"KabuRadar {mode_label}",
        now.strftime("%Y-%m-%d %H:%M JST"),
    ]
    header = format_summary_header()
    if header:
        body.append(header)
    body.append("— 損益上位 —")
    body.extend(lines)
    pages = pages_public_url()
    if pages:
        body.append(f"Web: {pages}")
    run_url = workflow_run_url()
    if run_url:
        body.append(f"Log: {run_url}")
    return notify_optional(body, stance)


def notify_from_payload(payload: dict, *, force: bool = False) -> bool:
    """publish 後の data.json 相当ペイロードから当日・特別シグナルを LINE 送信。"""
    from datetime import timezone

    from kaburadar3.notifications.line_state import already_notified, mark_notified
    from kaburadar3.publishing.ci_meta import pages_public_url, workflow_run_url
    from kaburadar3.settings.runtime import RuntimeConfig

    runtime = RuntimeConfig.from_dict(payload.get("runtime") or {})
    today = payload.get("today") or {}
    trade_date = today.get("trade_date") or "—"
    now = datetime.now(timezone.utc).astimezone()

    if not force and already_notified(trade_date):
        print(f"LINE: {trade_date} は送信済みのためスキップします。")
        return False

    body: list[str] = [
        f"KabuRadar {payload.get('mode', 'LO')}",
        now.strftime("%Y-%m-%d %H:%M JST"),
        f"対象日: {trade_date}",
    ]

    if runtime.notify_today_buy:
        buys = today.get("new_buy") or []
        body.append(f"— 今日の買い（新買）{len(buys)}件 —")
        if buys:
            for row in buys:
                body.append(format_signal_row(row))
        else:
            body.append("なし")

    if runtime.notify_today_sellback:
        backs = today.get("sellback") or []
        body.append(f"— 今日の返売り {len(backs)}件 —")
        if backs:
            for row in backs:
                body.append(format_signal_row(row))
        else:
            body.append("なし")

    for line in payload.get("line_events") or []:
        body.append(line)

    if runtime.notify_summary_top:
        from kaburadar3.notifications.summary import format_summary_header, format_top_symbols

        header = format_summary_header()
        if header:
            body.append(header)
        body.extend(format_top_symbols(limit=10))

    pages = pages_public_url()
    if pages:
        body.append(f"詳細: {pages}")

    run_url = workflow_run_url()
    if run_url:
        body.append(f"Log: {run_url}")

    sent = notify_optional(body, "")
    if sent:
        mark_notified(trade_date)
    return sent
