from __future__ import annotations

from kaburadar3.settings import git_publish


def test_resolve_publish_branch_explicit(monkeypatch) -> None:
    monkeypatch.setenv("KABURADAR_GIT_BRANCH", "develop")
    monkeypatch.setattr(git_publish, "_detect_origin_default_branch", lambda: "main")
    assert git_publish.resolve_publish_branch() == "develop"


def test_resolve_publish_branch_from_origin(monkeypatch) -> None:
    monkeypatch.delenv("KABURADAR_GIT_BRANCH", raising=False)
    monkeypatch.setattr(git_publish, "_detect_origin_default_branch", lambda: "main")
    monkeypatch.setattr(git_publish, "_current_branch", lambda: "feature")
    assert git_publish.resolve_publish_branch() == "main"


def test_resolve_publish_branch_fallback_master(monkeypatch) -> None:
    monkeypatch.delenv("KABURADAR_GIT_BRANCH", raising=False)
    monkeypatch.setattr(git_publish, "_detect_origin_default_branch", lambda: None)
    monkeypatch.setattr(git_publish, "_current_branch", lambda: None)
    assert git_publish.resolve_publish_branch() == "master"
