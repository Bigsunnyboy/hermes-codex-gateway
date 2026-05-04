import json

from hermes_local_agent_gateway.config import load_config


def test_load_config_parses_codex_env_and_output_cap(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "workspace_roots": [str(tmp_path / "projects")],
                "repo_aliases": {},
                "artifact_root": str(tmp_path / "artifacts"),
                "worktree_root": str(tmp_path / "worktrees"),
                "session_root": str(tmp_path / "sessions"),
                "codex_env": {
                    "HTTPS_PROXY": "http://127.0.0.1:7890",
                    "EMPTY": "",
                },
                "max_output_bytes": 1234,
            }
        ),
        encoding="utf-8",
    )

    cfg = load_config(path)

    assert cfg.codex_env == {
        "HTTPS_PROXY": "http://127.0.0.1:7890",
        "EMPTY": "",
    }
    assert cfg.max_output_bytes == 1234
