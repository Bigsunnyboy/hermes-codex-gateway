from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import write_json
from .identity import safe_id


def load_workspace_session(session_root: Path, workspace_id: str | None) -> dict[str, Any] | None:
    if not workspace_id:
        return None
    path = _session_path(session_root, workspace_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_workspace_session(
    session_root: Path,
    *,
    workspace_id: str | None,
    codex_session_id: str | None,
    project_path: Path,
    execution_path: Path,
) -> None:
    if not workspace_id or not codex_session_id:
        return
    path = _session_path(session_root, workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        path,
        {
            "workspace_id": workspace_id,
            "codex_session_id": codex_session_id,
            "project_path": str(project_path),
            "execution_path": str(execution_path),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _session_path(session_root: Path, workspace_id: str) -> Path:
    return session_root.expanduser().resolve() / f"{safe_id(workspace_id)}.json"
