from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def new_task_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"agent_{timestamp}_{uuid4().hex[:8]}"


def create_artifact_dir(root: Path, task_id: str) -> Path:
    path = root.expanduser().resolve() / task_id
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


IGNORED_FINGERPRINT_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".omx",
    ".playwright-cli",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}

SENSITIVE_FINGERPRINT_PATTERNS = (".env", "*.key", "*secret*", "auth.json", "credentials*")


def _is_sensitive_relative_path(path: Path) -> bool:
    return any(
        fnmatch.fnmatch(part.lower(), pattern)
        for part in path.parts
        for pattern in SENSITIVE_FINGERPRINT_PATTERNS
    )


def workspace_fingerprint(project_path: Path) -> str:
    """Hash non-sensitive file contents plus metadata to detect read-mode mutations."""
    digest = hashlib.sha256()
    root = project_path.resolve()

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            name for name in dirnames if name not in IGNORED_FINGERPRINT_DIRS
        )
        current = Path(dirpath)
        rel_dir = current.relative_to(root)

        for dirname in dirnames:
            rel_path = rel_dir / dirname
            digest.update(f"D\0{rel_path.as_posix()}\0".encode("utf-8"))

        for filename in sorted(filenames):
            path = current / filename
            rel_path = path.relative_to(root)
            try:
                stat = path.lstat()
            except OSError as exc:
                digest.update(f"E\0{rel_path.as_posix()}\0{type(exc).__name__}\0".encode("utf-8"))
                continue

            rel_text = rel_path.as_posix()
            digest.update(
                f"F\0{rel_text}\0{stat.st_mode}\0{stat.st_size}\0{stat.st_mtime_ns}\0".encode(
                    "utf-8"
                )
            )
            if _is_sensitive_relative_path(rel_path) or not path.is_file() or path.is_symlink():
                digest.update(b"<metadata-only>\0")
                continue

            try:
                with path.open("rb") as file:
                    for chunk in iter(lambda: file.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError as exc:
                digest.update(f"E\0{rel_text}\0{type(exc).__name__}\0".encode("utf-8"))

    return digest.hexdigest()


def capture_git(project_path: Path, artifact_dir: Path, *, prefix: str) -> None:
    commands = {
        "status": ["git", "-C", str(project_path), "status", "--short"],
        "diff_stat": ["git", "-C", str(project_path), "diff", "--stat"],
        "diff": ["git", "-C", str(project_path), "diff"],
    }
    for name, command in commands.items():
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )
        output = completed.stdout
        if completed.stderr:
            output += ("\n" if output else "") + completed.stderr
        (artifact_dir / f"{prefix}_{name}.txt").write_text(output, encoding="utf-8")
