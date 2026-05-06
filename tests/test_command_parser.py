from hermes_agent_gateway.command_parser import parse_agent_command


def test_parse_agent_slash_command_with_repo_workspace_session_and_verify() -> None:
    parsed = parse_agent_command(
        """/agent runner=codex repo=example-repo mode=write workspace=example-browser-fix session=019dec95-ea93-7170-805a-665a31137743 verify=pytest,ruff
修复浏览器 ask 成功路径。
不要读取 .env。"""
    )

    assert parsed.runner == "codex"
    assert parsed.repo == "example-repo"
    assert parsed.path is None
    assert parsed.mode == "write"
    assert parsed.workspace_id == "example-browser-fix"
    assert parsed.agent_session_id == "019dec95-ea93-7170-805a-665a31137743"
    assert parsed.verify_commands == ["pytest", "ruff"]
    assert parsed.prompt == "修复浏览器 ask 成功路径。\n不要读取 .env。"


def test_parse_agent_slash_command_with_absolute_path() -> None:
    parsed = parse_agent_command(
        "/agent runner=codex path=/home/projects/example-repo mode=read workspace=analysis\n总结风险。"
    )

    assert parsed.runner == "codex"
    assert parsed.repo is None
    assert parsed.path == "/home/projects/example-repo"
    assert parsed.mode == "read"
    assert parsed.workspace_id == "analysis"
    assert parsed.prompt == "总结风险。"


def test_parse_agent_slash_command_with_allowed_write_paths() -> None:
    parsed = parse_agent_command(
        "/agent runner=codex path=/home/projects/app mode=write workspace=fix allow=generated.txt,docs/report.md\n创建文件。"
    )

    assert parsed.allowed_paths == ["generated.txt", "docs/report.md"]
    assert parsed.to_task_payload()["allowed_paths"] == ["generated.txt", "docs/report.md"]


def test_parse_rejects_missing_runner() -> None:
    try:
        parse_agent_command("/agent repo=example-repo mode=read\nAnalyze.")
    except ValueError as exc:
        assert "runner" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parse_rejects_old_command_without_exact_literal() -> None:
    old_command = "/" + "codex"
    try:
        parse_agent_command(f"{old_command} runner=codex mode=read\nAnalyze.")
    except ValueError as exc:
        assert "/agent" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_parse_rejects_agent_prefix_that_is_not_command() -> None:
    try:
        parse_agent_command("/agentx runner=codex mode=read\nAnalyze.")
    except ValueError as exc:
        assert "/agent" in str(exc)
    else:
        raise AssertionError("expected ValueError")
