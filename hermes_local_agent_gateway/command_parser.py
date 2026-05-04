from __future__ import annotations

import shlex
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CodexCommand:
    repo: str | None
    path: str | None
    mode: str
    prompt: str
    workspace_id: str | None = None
    codex_session_id: str | None = None
    verify_commands: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)

    def to_task_payload(self) -> dict[str, object]:
        return {
            "repo": self.repo,
            "path": self.path,
            "mode": self.mode,
            "prompt": self.prompt,
            "workspace_id": self.workspace_id,
            "codex_session_id": self.codex_session_id,
            "verify_commands": self.verify_commands,
            "allowed_paths": self.allowed_paths,
        }


def parse_codex_command(text: str) -> CodexCommand:
    lines = text.strip().splitlines()
    if not lines:
        raise ValueError("Expected /codex command.")

    head = lines[0].strip()
    if not head.startswith("/codex"):
        raise ValueError("Expected /codex command.")

    options = _parse_options(head[len("/codex") :].strip())
    prompt = "\n".join(lines[1:]).strip()
    if not prompt:
        raise ValueError("Prompt is required after /codex options.")

    verify_commands = _split_csv(options.get("verify", ""))
    allowed_paths = _split_csv(options.get("allow", "") or options.get("allowed", ""))
    return CodexCommand(
        repo=options.get("repo"),
        path=options.get("path"),
        mode=options.get("mode", "read"),
        workspace_id=options.get("workspace") or options.get("workspace_id"),
        codex_session_id=options.get("session") or options.get("codex_session_id"),
        verify_commands=verify_commands,
        allowed_paths=allowed_paths,
        prompt=prompt,
    )


def _parse_options(raw: str) -> dict[str, str]:
    options: dict[str, str] = {}
    for token in shlex.split(raw):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        options[key.strip().lower()] = value.strip()
    return options


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
