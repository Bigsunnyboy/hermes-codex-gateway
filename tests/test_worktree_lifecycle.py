import subprocess
from pathlib import Path

from hermes_agent_gateway.worktree import inspect_workspace, remove_workspace


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    (repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True, text=True)


def test_inspect_workspace_reports_status_and_head(tmp_path: Path) -> None:
    repo = tmp_path / "projects" / "example-repo"
    _init_repo(repo)

    info = inspect_workspace(repo)

    assert info["exists"] is True
    assert info["path"] == str(repo.resolve())
    assert len(info["head"]) == 40
    assert info["status"] == ""


def test_remove_workspace_uses_git_worktree_remove(tmp_path: Path) -> None:
    repo = tmp_path / "projects" / "example-repo"
    _init_repo(repo)
    worktree = tmp_path / "worktrees" / "example-repo" / "fix"
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )

    result = remove_workspace(repo, worktree)

    assert result["removed"] is True
    assert not worktree.exists()
