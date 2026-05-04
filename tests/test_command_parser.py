from hermes_local_agent_gateway.command_parser import parse_codex_command


def test_parse_codex_slash_command_with_repo_workspace_session_and_verify() -> None:
    parsed = parse_codex_command(
        """/codex repo=example-repo mode=write workspace=example-browser-fix session=019dec95-ea93-7170-805a-665a31137743 verify=pytest,ruff
修复浏览器 ask 成功路径。
不要读取 .env。"""
    )

    assert parsed.repo == "example-repo"
    assert parsed.path is None
    assert parsed.mode == "write"
    assert parsed.workspace_id == "example-browser-fix"
    assert parsed.codex_session_id == "019dec95-ea93-7170-805a-665a31137743"
    assert parsed.verify_commands == ["pytest", "ruff"]
    assert parsed.prompt == "修复浏览器 ask 成功路径。\n不要读取 .env。"


def test_parse_codex_slash_command_with_absolute_path() -> None:
    parsed = parse_codex_command(
        "/codex path=/home/projects/example-repo mode=read workspace=analysis\n总结风险。"
    )

    assert parsed.repo is None
    assert parsed.path == "/home/projects/example-repo"
    assert parsed.mode == "read"
    assert parsed.workspace_id == "analysis"
    assert parsed.prompt == "总结风险。"


def test_parse_codex_slash_command_with_allowed_write_paths() -> None:
    parsed = parse_codex_command(
        "/codex path=/home/projects/app mode=write workspace=fix allow=generated.txt,docs/report.md\n创建文件。"
    )

    assert parsed.allowed_paths == ["generated.txt", "docs/report.md"]
    assert parsed.to_task_payload()["allowed_paths"] == ["generated.txt", "docs/report.md"]


def test_parse_rejects_non_codex_command() -> None:
    try:
        parse_codex_command("/agent status")
    except ValueError as exc:
        assert "/codex" in str(exc)
    else:
        raise AssertionError("expected ValueError")
