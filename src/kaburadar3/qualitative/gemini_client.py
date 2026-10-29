"""Gemini API クライアント."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from kaburadar3.settings.loader import load_project_env

# 混雑・一時障害でリトライするキーワード
_RETRY_MARKERS = (
    "503",
    "504",
    "429",
    "UNAVAILABLE",
    "DEADLINE_EXCEEDED",
    "RESOURCE_EXHAUSTED",
    "high demand",
    "try again",
)
_RETRY_IN_RE = re.compile(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _is_retryable(exc: BaseException) -> bool:
    msg = str(exc)
    # 日次枠切れは待っても戻らない
    if "per day" in msg.lower() or "requests per day" in msg.lower():
        return False
    return any(m in msg for m in _RETRY_MARKERS)


def _retry_delay_sec(exc: BaseException, attempt: int, base_delay_sec: float) -> float:
    msg = str(exc)
    m = _RETRY_IN_RE.search(msg)
    if m:
        return max(float(m.group(1)) + 1.0, base_delay_sec)
    return base_delay_sec * (2 ** (attempt - 1))


def generate_json(
    prompt: str,
    model: str | None = None,
    *,
    max_attempts: int = 4,
    base_delay_sec: float = 2.0,
) -> dict[str, Any]:
    load_project_env()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model_name = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed") from exc

    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 90_000},
    )
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )
            text = getattr(response, "text", None) or ""
            if not text and getattr(response, "candidates", None):
                parts = response.candidates[0].content.parts
                text = "".join(getattr(p, "text", "") or "" for p in parts)
            return _extract_json(text)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_attempts or not _is_retryable(exc):
                raise
            delay = _retry_delay_sec(exc, attempt, base_delay_sec)
            print(f"Gemini retry {attempt}/{max_attempts} after {delay:.0f}s ({exc})")
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
