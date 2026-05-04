from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GatewayConfig:
    workspace_roots: list[Path]
    repo_aliases: dict[str, Path]
    artifact_root: Path
    worktree_root: Path
    session_root: Path
    codex_executable: str = "codex"
    worktree_archive_root: Path | None = None
    max_workspaces: int = 20
    max_worktree_bytes: int = 5 * 1024 * 1024 * 1024
    worker_cron_name: str = "codex-queue-worker"
    worker_cron_schedule: str = "every 1m"
    codex_env: dict[str, str] | None = None
    max_output_bytes: int = 10 * 1024 * 1024
    approval_allowed_user_ids: list[str] | None = None
    approval_allowed_chat_ids: list[str] | None = None


def default_config() -> GatewayConfig:
    hermes_home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes")))
    workspace_root = Path(os.getenv("HERMES_AGENT_GATEWAY_WORKSPACE_ROOT", "/home/projects"))
    return GatewayConfig(
        workspace_roots=[workspace_root],
        repo_aliases={"example-repo": workspace_root / "example-repo"},
        artifact_root=hermes_home / "agent_tasks",
        worktree_root=hermes_home / "worktrees",
        session_root=hermes_home / "agent_sessions",
        codex_executable=os.getenv("CODEX_EXECUTABLE", "codex"),
        worktree_archive_root=hermes_home / "worktree_archives",
        approval_allowed_user_ids=_csv_env("HERMES_AGENT_GATEWAY_APPROVAL_USERS"),
        approval_allowed_chat_ids=_csv_env("HERMES_AGENT_GATEWAY_APPROVAL_CHATS"),
    )


def load_config(config_path: Path | None = None) -> GatewayConfig:
    cfg = default_config()
    path = config_path or Path(__file__).resolve().parents[1] / "config.json"
    if not path.exists():
        return cfg

    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    workspace_roots = [
        Path(value)
        for value in data.get("workspace_roots", [str(root) for root in cfg.workspace_roots])
    ]
    repo_aliases = {
        str(alias): Path(value)
        for alias, value in data.get(
            "repo_aliases",
            {alias: str(path) for alias, path in cfg.repo_aliases.items()},
        ).items()
    }
    artifact_root = Path(data.get("artifact_root", str(cfg.artifact_root)))
    worktree_root = Path(data.get("worktree_root", str(cfg.worktree_root)))
    session_root = Path(data.get("session_root", str(cfg.session_root)))
    codex_executable = str(data.get("codex_executable", cfg.codex_executable))
    worktree_archive_root = Path(
        data.get("worktree_archive_root", str(cfg.worktree_archive_root))
    )
    return GatewayConfig(
        workspace_roots=workspace_roots,
        repo_aliases=repo_aliases,
        artifact_root=artifact_root,
        worktree_root=worktree_root,
        session_root=session_root,
        codex_executable=codex_executable,
        worktree_archive_root=worktree_archive_root,
        max_workspaces=int(data.get("max_workspaces", cfg.max_workspaces)),
        max_worktree_bytes=int(data.get("max_worktree_bytes", cfg.max_worktree_bytes)),
        worker_cron_name=str(data.get("worker_cron_name", cfg.worker_cron_name)),
        worker_cron_schedule=str(data.get("worker_cron_schedule", cfg.worker_cron_schedule)),
        codex_env=_string_dict(data.get("codex_env", cfg.codex_env or {})),
        max_output_bytes=int(data.get("max_output_bytes", cfg.max_output_bytes)),
        approval_allowed_user_ids=_string_list(
            data.get("approval_allowed_user_ids", cfg.approval_allowed_user_ids or [])
        ),
        approval_allowed_chat_ids=_string_list(
            data.get("approval_allowed_chat_ids", cfg.approval_allowed_chat_ids or [])
        ),
    )


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key).strip(): str(item)
        for key, item in value.items()
        if str(key).strip()
    }
