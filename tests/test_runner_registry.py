from hermes_agent_gateway.config import GatewayConfig
from hermes_agent_gateway.runners.registry import (
    enabled_runner_ids,
    get_runner_definition,
)


def test_runtime_registry_exposes_only_enabled_codex_runner(tmp_path):
    assert enabled_runner_ids() == ["codex"]

    definition = get_runner_definition(" Codex ")

    assert definition.id == "codex"
    assert definition.capabilities.supports_read is True
    assert definition.capabilities.supports_write is True
    assert definition.capabilities.supports_resume is True
    assert definition.capabilities.dangerous_modes_disabled is True

    cfg = GatewayConfig(
        workspace_roots=[tmp_path],
        repo_aliases={},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )
    runner = definition.create_runner(cfg)
    assert runner.__class__.__name__ == "CodexCliRunner"


def test_runtime_registry_rejects_reserved_future_runners():
    for runner_id in ("claude-code", "qoder", "deepseek-tui", "unknown"):
        try:
            get_runner_definition(runner_id)
        except ValueError as exc:
            assert "enabled runner" in str(exc)
            assert "codex" in str(exc)
        else:
            raise AssertionError(f"expected {runner_id} to be rejected")
