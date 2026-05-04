from pathlib import Path

import pytest

from hermes_local_agent_gateway.config import GatewayConfig
from hermes_local_agent_gateway.policy import PolicyError, resolve_target


def _config(tmp_path: Path) -> GatewayConfig:
    root = tmp_path / "projects"
    repo = root / "example-repo"
    repo.mkdir(parents=True)
    return GatewayConfig(
        workspace_roots=[root],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )


def test_resolves_repo_alias_inside_workspace(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    resolved = resolve_target(cfg, repo="example-repo", path=None, mode="read")

    assert resolved == (tmp_path / "projects" / "example-repo").resolve()


def test_resolves_explicit_path_inside_workspace(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    target = tmp_path / "projects" / "example-repo"

    resolved = resolve_target(cfg, repo=None, path=str(target), mode="read")

    assert resolved == target.resolve()


def test_rejects_repo_and_path_together(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    with pytest.raises(PolicyError, match="exactly one"):
        resolve_target(cfg, repo="example-repo", path=str(tmp_path), mode="read")


def test_rejects_path_outside_workspace(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(PolicyError, match="workspace"):
        resolve_target(cfg, repo=None, path=str(outside), mode="read")


def test_rejects_sensitive_target_path(tmp_path: Path) -> None:
    cfg = _config(tmp_path)
    sensitive = tmp_path / "projects" / "example-repo" / "auth.json"
    sensitive.touch()

    with pytest.raises(PolicyError, match="sensitive"):
        resolve_target(cfg, repo=None, path=str(sensitive), mode="read")


def test_write_mode_requires_git_repo(tmp_path: Path) -> None:
    cfg = _config(tmp_path)

    with pytest.raises(PolicyError, match="Git"):
        resolve_target(cfg, repo="example-repo", path=None, mode="write")
