from __future__ import annotations

import shlex
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentCommand:
    runner: str
    repo: str | None
    path: str | None
    mode: str
    prompt: str
    workspace_id: str | None = None
    agent_session_id: str | None = None
    verify_commands: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)

    def to_task_payload(self) -> dict[str, object]:
        return {
            "runner": self.runner,
            "repo": self.repo,
            "path": self.path,
            "mode": self.mode,
            "prompt": self.prompt,
            "workspace_id": self.workspace_id,
            "agent_session_id": self.agent_session_id,
            "verify_commands": self.verify_commands,
            "allowed_paths": self.allowed_paths,
        }


def parse_agent_command(text: str) -> AgentCommand:
    lines = text.strip().splitlines()
    if not lines:
        raise ValueError("Expected /agent command.")

    head = lines[0].strip()
    if not _matches_command(head, "/agent"):
        raise ValueError("Expected /agent command.")

    options = _parse_options(head[len("/agent") :].strip())
    prompt = "\n".join(lines[1:]).strip()
    if not prompt:
        raise ValueError("Prompt is required after /agent options.")

    verify_commands = _split_csv(options.get("verify", ""))
    allowed_paths = _split_csv(options.get("allow", "") or options.get("allowed", ""))
    runner = str(options.get("runner") or "").strip().lower()
    if not runner:
        raise ValueError("runner is required for /agent commands.")
    if runner != "codex":
        raise ValueError("unsupported runner: " + runner)
    return AgentCommand(
        runner=runner,
        repo=options.get("repo"),
        path=options.get("path"),
        mode=options.get("mode", "read"),
        workspace_id=options.get("workspace") or options.get("workspace_id"),
        agent_session_id=options.get("session") or options.get("agent_session_id"),
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


def _matches_command(line: str, command: str) -> bool:
    return line == command or line.startswith(command + " ")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
