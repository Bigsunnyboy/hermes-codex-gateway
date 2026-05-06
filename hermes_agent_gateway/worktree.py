from __future__ import annotations

import subprocess
import tarfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

from .identity import safe_id
from .policy import SENSITIVE_PATTERNS


class WorktreeError(RuntimeError):
    """Raised when an isolated Git worktree cannot be prepared."""


@dataclass(frozen=True)
class ExecutionWorkspace:
    original_path: Path
    execution_path: Path
    isolation_mode: str
    workspace_id: str | None


def prepare_execution_workspace(
    project_path: Path,
    *,
    worktree_root: Path,
    task_id: str,
    workspace_id: str | None,
    max_workspaces: int | None = None,
    max_worktree_bytes: int | None = None,
) -> ExecutionWorkspace:
    if not _has_git_head(project_path):
        return ExecutionWorkspace(
            original_path=project_path,
            execution_path=project_path,
            isolation_mode="direct",
            workspace_id=None,
        )

    clean_workspace_id = safe_id(workspace_id or task_id)
    repo_id = safe_id(project_path.name)
    worktree_path = worktree_root.expanduser().resolve() / repo_id / clean_workspace_id
    if worktree_path.exists():
        return ExecutionWorkspace(
            original_path=project_path,
            execution_path=worktree_path.resolve(),
            isolation_mode="git-worktree",
            workspace_id=clean_workspace_id,
        )

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    quota = workspace_quota_report(
        worktree_root,
        max_workspaces=max_workspaces or 0,
        max_bytes=max_worktree_bytes or 0,
    )
    if max_workspaces and int(quota["workspace_count"]) >= max_workspaces:
        quota["over_quota"] = True
        reasons = list(quota.get("reasons", []))
        if "count" not in reasons:
            reasons.append("count")
        quota["reasons"] = reasons
    if quota["over_quota"]:
        raise WorktreeError(
            "worktree quota exceeded: "
            + ", ".join(str(reason) for reason in quota.get("reasons", []))
        )
    completed = subprocess.run(
        ["git", "-C", str(project_path), "worktree", "add", "--detach", str(worktree_path), "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git worktree error"
        raise WorktreeError(detail)

    return ExecutionWorkspace(
        original_path=project_path,
        execution_path=worktree_path.resolve(),
        isolation_mode="git-worktree",
        workspace_id=clean_workspace_id,
    )


def _has_git_head(path: Path) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--verify", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def inspect_workspace(path: Path) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return {"exists": False, "path": str(resolved)}
    head = subprocess.run(
        ["git", "-C", str(resolved), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    status = subprocess.run(
        ["git", "-C", str(resolved), "status", "--short"],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "exists": True,
        "path": str(resolved),
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "status": status.stdout if status.returncode == 0 else status.stderr,
    }


def inspect_workspace_conflicts(path: Path) -> dict[str, object]:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return {"exists": False, "path": str(resolved), "dirty": False, "conflict_files": []}
    status = subprocess.run(
        ["git", "-C", str(resolved), "status", "--short"],
        text=True,
        capture_output=True,
        check=False,
    )
    conflict_files: list[str] = []
    for file_path in _iter_workspace_files(resolved):
        try:
            text = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "<<<<<<<" in text and "=======" in text and ">>>>>>>" in text:
            conflict_files.append(file_path.relative_to(resolved).as_posix())
    return {
        "exists": True,
        "path": str(resolved),
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else True,
        "status": status.stdout if status.returncode == 0 else status.stderr,
        "conflict_files": sorted(conflict_files),
    }


def remove_workspace(repo_path: Path, worktree_path: Path) -> dict[str, object]:
    resolved = worktree_path.expanduser().resolve()
    completed = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "remove", "--force", str(resolved)],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git worktree remove error"
        raise WorktreeError(detail)
    return {
        "removed": True,
        "path": str(resolved),
    }


def archive_workspace(repo_path: Path, worktree_path: Path, archive_root: Path) -> dict[str, object]:
    resolved = worktree_path.expanduser().resolve()
    if not resolved.exists():
        return {"archived": False, "removed": False, "path": str(resolved), "reason": "missing"}

    archive_root = archive_root.expanduser().resolve()
    archive_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = archive_root / f"{safe_id(resolved.parent.name)}-{safe_id(resolved.name)}-{timestamp}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        for file_path in _iter_workspace_files(resolved):
            rel_path = file_path.relative_to(resolved)
            tar.add(file_path, arcname=(Path(resolved.name) / rel_path).as_posix())

    removed = remove_workspace(repo_path, resolved)
    return {
        "archived": True,
        "removed": removed["removed"],
        "path": str(resolved),
        "archive_path": str(archive_path),
    }


def workspace_quota_report(
    worktree_root: Path,
    *,
    max_workspaces: int,
    max_bytes: int,
) -> dict[str, object]:
    root = worktree_root.expanduser().resolve()
    workspaces: list[Path] = []
    total_bytes = 0
    if root.exists():
        for repo_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            for workspace in sorted(path for path in repo_dir.iterdir() if path.is_dir()):
                workspaces.append(workspace)
                total_bytes += _directory_size(workspace)
    reasons: list[str] = []
    if max_workspaces and len(workspaces) > max_workspaces:
        reasons.append("count")
    if max_bytes and total_bytes > max_bytes:
        reasons.append("bytes")
    return {
        "root": str(root),
        "workspace_count": len(workspaces),
        "total_bytes": total_bytes,
        "max_workspaces": max_workspaces,
        "max_bytes": max_bytes,
        "over_quota": bool(reasons),
        "reasons": reasons,
        "workspaces": [str(path) for path in workspaces],
    }


def _iter_workspace_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        rel_path = path.relative_to(root)
        if ".git" in rel_path.parts or _is_sensitive_relative_path(rel_path):
            continue
        yield path


def _directory_size(root: Path) -> int:
    total = 0
    for path in _iter_workspace_files(root):
        try:
            total += path.lstat().st_size
        except OSError:
            continue
    return total


def _is_sensitive_relative_path(path: Path) -> bool:
    import fnmatch

    return any(
        fnmatch.fnmatch(part.lower(), pattern)
        for part in path.parts
        for pattern in SENSITIVE_PATTERNS
    )
