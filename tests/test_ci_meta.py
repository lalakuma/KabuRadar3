from __future__ import annotations

from kaburadar3.publishing.ci_meta import build_run_meta, pages_public_url, workflow_run_url


def test_pages_url_from_repository(monkeypatch) -> None:
    monkeypatch.delenv("KABURADAR_PAGES_URL", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "lalakuma/KabuRadar3")
    assert pages_public_url() == "https://lalakuma.github.io/KabuRadar3"


def test_pages_url_explicit(monkeypatch) -> None:
    monkeypatch.setenv("KABURADAR_PAGES_URL", "https://example.com/app/")
    assert pages_public_url() == "https://example.com/app"


def test_workflow_run_url(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "99")
    assert workflow_run_url() == "https://github.com/owner/repo/actions/runs/99"


def test_build_run_meta_on_actions(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_REPOSITORY", "lalakuma/KabuRadar3")
    monkeypatch.setenv("GITHUB_RUN_ID", "1")
    meta = build_run_meta()
    assert meta["source"] == "github-actions"
    assert meta["event"] == "schedule"
    assert "pages_url" in meta
    assert "workflow_url" in meta
