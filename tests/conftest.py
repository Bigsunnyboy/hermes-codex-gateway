from pathlib import Path

import pytest

from hermes_agent_gateway.config import GatewayConfig


@pytest.fixture
def gateway_config(tmp_path: Path) -> GatewayConfig:
    workspace = tmp_path / "projects"
    repo = workspace / "example-repo"
    return GatewayConfig(
        workspace_roots=[workspace],
        repo_aliases={"example-repo": repo},
        artifact_root=tmp_path / "artifacts",
        worktree_root=tmp_path / "worktrees",
        session_root=tmp_path / "sessions",
        codex_executable="codex",
    )
