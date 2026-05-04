from pathlib import Path

from hermes_local_agent_gateway.runner import CodexCliRunner, _copy_limited_stream


def test_builds_read_only_codex_exec_command() -> None:
    runner = CodexCliRunner(codex_executable="codex")

    command = runner.build_command(
        project_path=Path("/home/projects/example-repo"),
        prompt="Analyze only.",
        mode="read",
    )

    assert command == [
        "codex",
        "exec",
        "--cd",
        "/home/projects/example-repo",
        "--sandbox",
        "read-only",
        "--json",
        "Analyze only.",
    ]


def test_builds_workspace_write_codex_exec_command() -> None:
    runner = CodexCliRunner(codex_executable="codex")

    command = runner.build_command(
        project_path=Path("/home/projects/example-repo"),
        prompt="Fix tests.",
        mode="write",
    )

    assert "--sandbox" in command
    assert "workspace-write" in command
    assert "danger-full-access" not in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_builds_resume_codex_exec_command() -> None:
    runner = CodexCliRunner(codex_executable="codex")

    command = runner.build_command(
        project_path=Path("/home/projects/example-repo"),
        prompt="Continue.",
        mode="read",
        codex_session_id="019dec87-6e36-77e0-9430-093e3fd31d10",
    )

    assert command == [
        "codex",
        "exec",
        "--cd",
        "/home/projects/example-repo",
        "--sandbox",
        "read-only",
        "--json",
        "resume",
        "019dec87-6e36-77e0-9430-093e3fd31d10",
        "Continue.",
    ]


def test_build_env_uses_managed_codex_home_without_user_hooks(tmp_path: Path) -> None:
    source_home = tmp_path / "source-codex-home"
    gateway_home = tmp_path / "gateway-codex-home"
    source_home.mkdir()
    (source_home / "auth.json").write_text("{}", encoding="utf-8")
    (source_home / "config.toml").write_text(
        "\n".join(
            [
                "notify = [\"node\", \"omx-notify.js\"]",
                'model_reasoning_effort = "high"',
                'developer_instructions = "load omx"',
                'model = "gpt-5.5"',
                "",
                "[mcp_servers.omx_state]",
                'command = "node"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (source_home / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    runner = CodexCliRunner(
        codex_executable="codex",
        codex_home=gateway_home,
        source_codex_home=source_home,
    )

    env = runner.build_env()

    assert env["CODEX_HOME"] == str(gateway_home)
    assert (gateway_home / "auth.json").is_symlink()
    assert not (gateway_home / "hooks.json").exists()
    config = (gateway_home / "config.toml").read_text(encoding="utf-8")
    assert 'model = "gpt-5.5"' in config
    assert 'model_reasoning_effort = "high"' in config
    assert "notify" not in config
    assert "developer_instructions" not in config
    assert "mcp_servers" not in config


def test_build_env_applies_extra_env_but_preserves_managed_codex_home(tmp_path: Path) -> None:
    source_home = tmp_path / "source-codex-home"
    gateway_home = tmp_path / "gateway-codex-home"
    source_home.mkdir()
    runner = CodexCliRunner(
        codex_executable="codex",
        codex_home=gateway_home,
        source_codex_home=source_home,
        extra_env={
            "HTTPS_PROXY": "http://127.0.0.1:7890",
            "CODEX_HOME": "/tmp/should-not-win",
        },
    )

    env = runner.build_env()

    assert env["HTTPS_PROXY"] == "http://127.0.0.1:7890"
    assert env["CODEX_HOME"] == str(gateway_home)


def test_copy_limited_stream_truncates_runaway_output() -> None:
    from io import StringIO

    target = StringIO()

    _copy_limited_stream(iter(["abc", "def", "ghi"]), target, 5)

    assert target.getvalue() == "abcde\n[output truncated by hermes-codex-gateway]\n"


def test_run_captures_limited_subprocess_output(tmp_path: Path) -> None:
    fake_codex = tmp_path / "fake-codex"
    fake_codex.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('abcdef')\n"
        "print('errabcdef', file=sys.stderr)\n"
        "sys.exit(7)\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    runner = CodexCliRunner(
        codex_executable=str(fake_codex),
        codex_home=tmp_path / "gateway-codex-home",
        source_codex_home=tmp_path / "source-codex-home",
        max_output_bytes=4,
    )
    stdout_path = tmp_path / "stdout.jsonl"
    stderr_path = tmp_path / "stderr.log"

    result = runner.run(
        project_path=tmp_path,
        prompt="Run.",
        mode="read",
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )

    assert result["returncode"] == 7
    assert stdout_path.read_text(encoding="utf-8").startswith("abcd\n[output truncated")
    assert stderr_path.read_text(encoding="utf-8").startswith("erra\n[output truncated")
