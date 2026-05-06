from __future__ import annotations

import shlex
from pathlib import Path


VERIFY_TEMPLATES = {
    "pytest": ["pytest"],
    "ruff": ["ruff"],
}


def expand_verify_templates(items: list[str] | None) -> list[str]:
    commands: list[str] = []
    for item in items or []:
        token = item.strip()
        if not token:
            continue
        if token in VERIFY_TEMPLATES:
            commands.extend(VERIFY_TEMPLATES[token])
            continue
        if token.startswith("file:"):
            rel_path = token.removeprefix("file:").strip()
            if not _is_safe_relative_path(rel_path):
                raise ValueError(f"Unsafe verify file template path: {rel_path}")
            commands.append(f"test -f {shlex.quote(rel_path)}")
            continue
        commands.append(token)
    return commands


def _is_safe_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts
