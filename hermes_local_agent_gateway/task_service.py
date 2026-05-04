from __future__ import annotations

from pathlib import PurePosixPath
from pathlib import Path
from typing import Any, Protocol

from .artifacts import capture_git, create_artifact_dir, new_task_id, workspace_fingerprint, write_json
from .config import GatewayConfig
from .policy import resolve_target
from .risk_policy import assess_task_risk
from .sessions import load_workspace_session, save_workspace_session
from .verify import run_verify_commands
from .verify_templates import expand_verify_templates
from .worktree import ExecutionWorkspace, prepare_execution_workspace


class Runner(Protocol):
    def run(
        self,
        *,
        project_path: Path,
        prompt: str,
        mode: str,
        stdout_path: Path,
        stderr_path: Path,
        codex_session_id: str | None = None,
    ) -> dict[str, Any]:
        ...


def create_codex_task(
    cfg: GatewayConfig,
    *,
    runner: Runner,
    repo: str | None,
    path: str | None,
    mode: str,
    prompt: str,
    workspace_id: str | None = None,
    codex_session_id: str | None = None,
    approved: bool = False,
    verify_commands: list[str] | None = None,
    allowed_paths: list[str] | None = None,
) -> dict[str, Any]:
    if not prompt.strip():
        raise ValueError("prompt is required")
    verify_commands = expand_verify_templates(verify_commands)
    allowed_paths = _sanitize_allowed_paths(allowed_paths)
    if mode != "write" and verify_commands:
        raise ValueError("verify_commands are only allowed for approved write tasks.")
    if mode != "write" and allowed_paths:
        raise ValueError("allowed_paths are only allowed for write tasks.")

    project_path = resolve_target(cfg, repo=repo, path=path, mode=mode)
    task_id = new_task_id()
    artifact_dir = create_artifact_dir(cfg.artifact_root, task_id)
    stdout_path = artifact_dir / "codex_stdout.jsonl"
    stderr_path = artifact_dir / "codex_stderr.log"

    workspace = ExecutionWorkspace(
        original_path=project_path,
        execution_path=project_path,
        isolation_mode="direct",
        workspace_id=None,
    )
    runner_result: dict[str, Any] = {
        "command": [],
        "returncode": None,
        "duration_seconds": None,
    }
    error = None
    risk = assess_task_risk(
        mode=mode,
        prompt=prompt,
        verify_commands=verify_commands,
        allowed_paths=allowed_paths,
    )
    try:
        workspace = prepare_execution_workspace(
            project_path,
            worktree_root=cfg.worktree_root,
            task_id=task_id,
            workspace_id=workspace_id,
            max_workspaces=cfg.max_workspaces,
            max_worktree_bytes=cfg.max_worktree_bytes,
        )
    except Exception as exc:
        error = f"WorktreeError: {exc}"

    execution_path = workspace.execution_path
    if risk.get("blocked"):
        capture_git(execution_path, artifact_dir, prefix="before")
        capture_git(execution_path, artifact_dir, prefix="after")
        payload = {
            "success": False,
            "status": "BLOCKED",
            "task_id": task_id,
            "mode": mode,
            "project_path": str(project_path),
            "execution_path": str(execution_path),
            "isolation_mode": workspace.isolation_mode,
            "workspace_id": workspace.workspace_id,
            "requested_codex_session_id": codex_session_id,
            "codex_session_id": None,
            "artifact_dir": str(artifact_dir),
            "command": [],
            "returncode": None,
            "duration_seconds": None,
            "workspace_changed": False,
            "verify_results": [],
            "allowed_paths": allowed_paths,
            "risk": risk,
            "prompt": prompt,
            "error": "Task blocked by write risk policy.",
        }
        write_json(artifact_dir / "task.json", payload)
        return payload

    if mode == "write" and not approved:
        capture_git(execution_path, artifact_dir, prefix="before")
        capture_git(execution_path, artifact_dir, prefix="after")
        payload = {
            "success": False,
            "status": "APPROVAL_REQUIRED",
            "task_id": task_id,
            "mode": mode,
            "project_path": str(project_path),
            "execution_path": str(execution_path),
            "isolation_mode": workspace.isolation_mode,
            "workspace_id": workspace.workspace_id,
            "requested_codex_session_id": codex_session_id,
            "codex_session_id": None,
            "artifact_dir": str(artifact_dir),
            "command": [],
            "returncode": None,
            "duration_seconds": None,
            "workspace_changed": False,
            "verify_results": [],
            "allowed_paths": allowed_paths,
            "risk": risk,
            "prompt": prompt,
            "error": "Write mode requires approval before Codex execution.",
        }
        write_json(artifact_dir / "task.json", payload)
        return payload

    saved_session = load_workspace_session(cfg.session_root, workspace.workspace_id)
    resume_session_id = codex_session_id or (saved_session or {}).get("codex_session_id")
    before_fingerprint = workspace_fingerprint(execution_path)
    capture_git(execution_path, artifact_dir, prefix="before")

    try:
        if error is None:
            runner_result = runner.run(
                project_path=execution_path,
                prompt=prompt,
                mode=mode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                codex_session_id=resume_session_id,
            )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            capture_git(execution_path, artifact_dir, prefix="after")
        except Exception as exc:
            capture_error = f"{type(exc).__name__}: {exc}"
            error = f"{error}; after capture failed: {capture_error}" if error else capture_error

    after_fingerprint = workspace_fingerprint(execution_path)
    before_status = _read_artifact_text(artifact_dir / "before_status.txt")
    after_status = _read_artifact_text(artifact_dir / "after_status.txt")
    workspace_changed = before_status != after_status or before_fingerprint != after_fingerprint
    if mode == "read" and workspace_changed:
        read_error = "Read-only task changed workspace content/status or concurrent workspace changes were detected."
        error = f"{error}; {read_error}" if error else read_error

    verify_results: list[dict[str, object]] = []
    if error is None and verify_commands:
        verify_results = run_verify_commands(
            execution_path=execution_path,
            artifact_dir=artifact_dir,
            commands=verify_commands,
        )
        failed_verify = [result for result in verify_results if result["returncode"] != 0]
        if failed_verify:
            error = "One or more verification commands failed."
    if mode == "write" and allowed_paths:
        unexpected_paths = _unexpected_changed_paths(after_status, allowed_paths)
        if unexpected_paths:
            policy_error = "Unexpected write changes outside allowlist: " + ", ".join(unexpected_paths)
            error = f"{error}; {policy_error}" if error else policy_error

    resolved_session_id = runner_result.get("codex_session_id") or resume_session_id
    save_workspace_session(
        cfg.session_root,
        workspace_id=workspace.workspace_id,
        codex_session_id=resolved_session_id,
        project_path=project_path,
        execution_path=execution_path,
    )

    payload = {
        "success": runner_result.get("returncode") == 0 and error is None,
        "status": "DONE" if runner_result.get("returncode") == 0 and error is None else "FAILED",
        "task_id": task_id,
        "mode": mode,
        "project_path": str(project_path),
        "execution_path": str(execution_path),
        "isolation_mode": workspace.isolation_mode,
        "workspace_id": workspace.workspace_id,
        "requested_codex_session_id": codex_session_id,
        "codex_session_id": resolved_session_id,
        "artifact_dir": str(artifact_dir),
        "command": runner_result.get("command", []),
        "returncode": runner_result.get("returncode"),
        "duration_seconds": runner_result.get("duration_seconds"),
        "workspace_changed": workspace_changed,
        "verify_results": verify_results,
        "allowed_paths": allowed_paths,
        "risk": risk,
        "prompt": prompt,
    }
    if error:
        payload["error"] = error
    write_json(artifact_dir / "task.json", payload)
    return payload


def _read_artifact_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _sanitize_allowed_paths(paths: list[str] | None) -> list[str]:
    allowed: list[str] = []
    for raw_path in paths or []:
        path = str(raw_path).replace("\\", "/").strip()
        if not path:
            continue
        if path.startswith("/"):
            raise ValueError("allowed_paths must be relative paths.")
        parts = PurePosixPath(path.rstrip("/")).parts
        if ".." in parts:
            raise ValueError("allowed_paths must not contain '..'.")
        allowed.append(path)
    return allowed


def _unexpected_changed_paths(status: str, allowed_paths: list[str]) -> list[str]:
    return [
        path
        for path in _changed_paths_from_status(status)
        if not _path_is_allowed(path, allowed_paths)
    ]


def _changed_paths_from_status(status: str) -> list[str]:
    changed_paths: list[str] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        raw_path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in raw_path:
            changed_paths.extend(path.strip() for path in raw_path.split(" -> ", 1) if path.strip())
        elif raw_path:
            changed_paths.append(raw_path)
    return changed_paths


def _path_is_allowed(path: str, allowed_paths: list[str]) -> bool:
    normalized_path = path.replace("\\", "/").strip()
    for allowed in allowed_paths:
        normalized_allowed = allowed.rstrip("/")
        if normalized_path == normalized_allowed:
            return True
        if normalized_path.startswith(f"{normalized_allowed}/"):
            return True
    return False
