"""GitHub Actions / Pages 向けの公開 URL・実行メタデータ."""

from __future__ import annotations

import os


def pages_public_url() -> str:
    explicit = os.getenv("KABURADAR_PAGES_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}"
    return ""


def workflow_run_url() -> str:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    run_id = os.getenv("GITHUB_RUN_ID", "").strip()
    if not repo or not run_id:
        return ""
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com").strip().rstrip("/")
    return f"{server}/{repo}/actions/runs/{run_id}"


def build_run_meta() -> dict:
    """CI 実行時に data.json へ載せる実行メタ。ローカルでは空に近い dict。"""
    meta: dict[str, str] = {}
    if os.getenv("GITHUB_ACTIONS", "").strip().lower() == "true":
        meta["source"] = "github-actions"
        event = os.getenv("GITHUB_EVENT_NAME", "").strip()
        if event:
            meta["event"] = event
        schedule = os.getenv("GITHUB_EVENT_SCHEDULE", "").strip()
        if schedule:
            meta["schedule"] = schedule
        repo = os.getenv("GITHUB_REPOSITORY", "").strip()
        if repo:
            meta["repository"] = repo
        pages = pages_public_url()
        if pages:
            meta["pages_url"] = pages
        run_url = workflow_run_url()
        if run_url:
            meta["workflow_url"] = run_url
    else:
        pages = pages_public_url()
        if pages:
            meta["pages_url"] = pages
    return meta
