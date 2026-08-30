"""GitHub Pages 用 push 先ブランチの解決."""

from __future__ import annotations

import os
import subprocess

from .paths import PROJECT_ROOT

try:
    from dotenv import load_dotenv
except Exception:  # noqa: BLE001
    def load_dotenv(*_args, **_kwargs):  # type: ignore[no-redef]
        return False


def resolve_publish_branch() -> str:
    """push 先ブランチ。KABURADAR_GIT_BRANCH → origin/HEAD → 現在ブランチ → master。"""
    load_dotenv(PROJECT_ROOT / ".env")
    explicit = os.getenv("KABURADAR_GIT_BRANCH", "").strip()
    if explicit:
        return explicit

    detected = _detect_origin_default_branch()
    if detected:
        return detected

    current = _current_branch()
    if current:
        return current

    return "master"


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _detect_origin_default_branch() -> str | None:
    result = _run_git(["symbolic-ref", "refs/remotes/origin/HEAD"])
    if result.returncode != 0 or not result.stdout.strip():
        return None
    ref = result.stdout.strip()
    if "/" in ref:
        return ref.rsplit("/", 1)[-1]
    return ref


def _current_branch() -> str | None:
    result = _run_git(["branch", "--show-current"])
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None
