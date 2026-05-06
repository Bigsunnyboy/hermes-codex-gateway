from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from ..config import GatewayConfig
from .codex import CodexCliRunner


class Runner(Protocol):
    def run(self, **kwargs) -> dict[str, object]:
        ...


@dataclass(frozen=True)
class RunnerCapabilities:
    supports_read: bool
    supports_write: bool
    supports_resume: bool
    supports_json_output: bool
    supports_permission_mode: bool
    dangerous_modes_disabled: bool


@dataclass(frozen=True)
class RunnerDefinition:
    id: str
    display_name: str
    capabilities: RunnerCapabilities
    create_runner: Callable[[GatewayConfig], Runner]


def _create_codex_runner(cfg: GatewayConfig) -> CodexCliRunner:
    return CodexCliRunner(
        codex_executable=cfg.codex_executable,
        extra_env=cfg.codex_env or {},
        max_output_bytes=cfg.max_output_bytes,
    )


_RUNNERS = {
    "codex": RunnerDefinition(
        id="codex",
        display_name="Codex",
        capabilities=RunnerCapabilities(
            supports_read=True,
            supports_write=True,
            supports_resume=True,
            supports_json_output=True,
            supports_permission_mode=True,
            dangerous_modes_disabled=True,
        ),
        create_runner=_create_codex_runner,
    ),
}


def enabled_runner_ids() -> list[str]:
    return sorted(_RUNNERS)


def get_runner_definition(runner_id: str) -> RunnerDefinition:
    normalized = normalize_runner_id(runner_id)
    try:
        return _RUNNERS[normalized]
    except KeyError:
        raise ValueError(_enabled_runner_error()) from None


def normalize_runner_id(runner_id: str) -> str:
    return str(runner_id or "").strip().lower()


def _enabled_runner_error() -> str:
    return "runner is required and must be an enabled runner: " + ", ".join(enabled_runner_ids())
