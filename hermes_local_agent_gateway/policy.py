from __future__ import annotations

import fnmatch
from pathlib import Path

from .config import GatewayConfig


class PolicyError(ValueError):
    """Raised when a requested Codex task violates gateway policy."""


SENSITIVE_PATTERNS = (".env", "*.key", "*secret*", "auth.json", "credentials*")


def _is_sensitive_path(path: Path) -> bool:
    for part in path.parts:
        lowered = part.lower()
        if any(fnmatch.fnmatch(lowered, pattern) for pattern in SENSITIVE_PATTERNS):
            return True
    return False


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_git_work_tree(path: Path) -> bool:
    git_marker = path / ".git"
    return git_marker.exists()


def resolve_target(
    cfg: GatewayConfig,
    *,
    repo: str | None,
    path: str | None,
    mode: str,
) -> Path:
    clean_repo = (repo or "").strip()
    clean_path = (path or "").strip()
    if bool(clean_repo) == bool(clean_path):
        raise PolicyError("Specify exactly one of repo or path.")

    if mode not in {"read", "write"}:
        raise PolicyError("mode must be one of: read, write.")

    if clean_repo:
        if clean_repo not in cfg.repo_aliases:
            raise PolicyError(f"Unknown repo alias: {clean_repo}")
        target = cfg.repo_aliases[clean_repo]
    else:
        target = Path(clean_path)
        if not target.is_absolute():
            raise PolicyError("path must be absolute.")

    resolved = target.expanduser().resolve()
    if _is_sensitive_path(resolved):
        raise PolicyError("Target path is sensitive and cannot be used.")

    roots = [root.expanduser().resolve() for root in cfg.workspace_roots]
    if not any(_is_under(resolved, root) for root in roots):
        raise PolicyError("Resolved target is outside allowed workspace roots.")

    if not resolved.exists():
        raise PolicyError(f"Resolved target does not exist: {resolved}")
    if not resolved.is_dir():
        raise PolicyError(f"Resolved target is not a directory: {resolved}")

    if mode == "write" and not _is_git_work_tree(resolved):
        raise PolicyError("write mode requires a Git work tree.")

    return resolved
