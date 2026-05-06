import tarfile
from pathlib import Path

from hermes_agent_gateway.worktree import (
    WorktreeError,
    archive_workspace,
    inspect_workspace_conflicts,
    prepare_execution_workspace,
    workspace_quota_report,
)


def test_archive_workspace_skips_sensitive_files_and_removes_worktree(tmp_path: Path) -> None:
    repo = tmp_path / "projects" / "example-repo"
    _init_repo(repo)
    worktree = tmp_path / "worktrees" / "example-repo" / "fix"
    import subprocess

    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(worktree), "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    (worktree / "notes.txt").write_text("keep\n", encoding="utf-8")
    (worktree / ".env").write_text("skip\n", encoding="utf-8")

    result = archive_workspace(repo, worktree, tmp_path / "archives")

    assert result["archived"] is True
    assert result["removed"] is True
    assert not worktree.exists()
    with tarfile.open(result["archive_path"], "r:gz") as tar:
        names = tar.getnames()
    assert any(name.endswith("notes.txt") for name in names)
    assert not any(name.endswith(".env") for name in names)


def test_workspace_quota_report_flags_count_limit(tmp_path: Path) -> None:
    root = tmp_path / "worktrees"
    (root / "example-repo" / "one").mkdir(parents=True)
    (root / "example-repo" / "two").mkdir(parents=True)

    result = workspace_quota_report(root, max_workspaces=1, max_bytes=10_000)

    assert result["workspace_count"] == 2
    assert result["over_quota"] is True
    assert "count" in result["reasons"]


def test_prepare_execution_workspace_blocks_creation_at_count_limit(tmp_path: Path) -> None:
    repo = tmp_path / "projects" / "example-repo"
    _init_repo(repo)
    root = tmp_path / "worktrees"
    (root / "example-repo" / "one").mkdir(parents=True)
    (root / "example-repo" / "two").mkdir(parents=True)

    try:
        prepare_execution_workspace(
            repo,
            worktree_root=root,
            task_id="new-task",
            workspace_id="three",
            max_workspaces=2,
            max_worktree_bytes=0,
        )
    except WorktreeError as exc:
        assert "quota" in str(exc)
    else:
        raise AssertionError("expected WorktreeError")


def test_inspect_workspace_conflicts_reports_dirty_and_conflict_markers(tmp_path: Path) -> None:
    repo = tmp_path / "projects" / "example-repo"
    _init_repo(repo)
    conflict_file = repo / "tracked.txt"
    conflict_file.write_text("<<<<<<< ours\nx\n=======\ny\n>>>>>>> theirs\n", encoding="utf-8")

    result = inspect_workspace_conflicts(repo)

    assert result["dirty"] is True
    assert "tracked.txt" in result["conflict_files"]


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    import subprocess

    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    (repo / "tracked.txt").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "initial"], check=True, capture_output=True, text=True)
