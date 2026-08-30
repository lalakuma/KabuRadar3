"""Gemini API クライアント."""

from __future__ import annotations

import json
import os
from typing import Any


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


def generate_json(prompt: str, model: str | None = None) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed") from exc

    client = genai.Client(api_key=api_key)
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
