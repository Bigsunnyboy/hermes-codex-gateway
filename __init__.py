from __future__ import annotations

try:
    from .hermes_local_agent_gateway.command_parser import parse_codex_command
    from .hermes_local_agent_gateway.config import load_config
    from .hermes_local_agent_gateway.delivery import deliver_task_result
    from .hermes_local_agent_gateway.feishu_router import (
        approval_action_allowed,
        build_card_action_callback_response,
        handle_pre_gateway_dispatch,
    )
    from .hermes_local_agent_gateway.policy import resolve_target
    from .hermes_local_agent_gateway.queue import FileTaskQueue
    from .hermes_local_agent_gateway.runner import CodexCliRunner
    from .hermes_local_agent_gateway.risk_policy import assess_task_risk
    from .hermes_local_agent_gateway.scheduler import ensure_worker_cron_job, run_next_queue_task
    from .hermes_local_agent_gateway.task_service import create_codex_task
    from .hermes_local_agent_gateway.verify_templates import expand_verify_templates
    from .hermes_local_agent_gateway.worktree import (
        archive_workspace,
        inspect_workspace,
        inspect_workspace_conflicts,
        remove_workspace,
        workspace_quota_report,
    )
except ImportError:
    from hermes_local_agent_gateway.command_parser import parse_codex_command
    from hermes_local_agent_gateway.config import load_config
    from hermes_local_agent_gateway.delivery import deliver_task_result
    from hermes_local_agent_gateway.feishu_router import (
        approval_action_allowed,
        build_card_action_callback_response,
        handle_pre_gateway_dispatch,
    )
    from hermes_local_agent_gateway.policy import resolve_target
    from hermes_local_agent_gateway.queue import FileTaskQueue
    from hermes_local_agent_gateway.runner import CodexCliRunner
    from hermes_local_agent_gateway.risk_policy import assess_task_risk
    from hermes_local_agent_gateway.scheduler import ensure_worker_cron_job, run_next_queue_task
    from hermes_local_agent_gateway.task_service import create_codex_task
    from hermes_local_agent_gateway.verify_templates import expand_verify_templates
    from hermes_local_agent_gateway.worktree import (
        archive_workspace,
        inspect_workspace,
        inspect_workspace_conflicts,
        remove_workspace,
        workspace_quota_report,
    )


CREATE_CODEX_TASK_SCHEMA = {
    "name": "create_codex_task",
    "description": "Create a governed local Codex task with workspace policy and artifact capture.",
    "parameters": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Optional configured repository alias, for example example-repo.",
            },
            "path": {
                "type": "string",
                "description": "Optional absolute project path under an allowed workspace root.",
            },
            "mode": {
                "type": "string",
                "enum": ["read", "write"],
                "description": "Execution mode. read uses Codex read-only sandbox; write uses workspace-write.",
            },
            "workspace_id": {
                "type": "string",
                "description": "Optional stable isolated worktree handle, for example example-browser-fix.",
            },
            "codex_session_id": {
                "type": "string",
                "description": "Optional Codex session/thread id to resume. If absent, the workspace_id saved session is reused when available.",
            },
            "verify_commands": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional verification commands to run in the execution worktree after Codex.",
            },
            "allowed_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional write-mode allowlist. Changed paths outside this list fail the task after Codex runs.",
            },
            "prompt": {
                "type": "string",
                "description": "Task prompt for Codex.",
            },
        },
        "required": ["mode", "prompt"],
    },
}

SUBMIT_CODEX_COMMAND_SCHEMA = {
    "name": "submit_codex_command",
    "description": "Parse a Feishu /codex command and enqueue it for asynchronous execution.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Full Feishu message text beginning with /codex."},
        },
        "required": ["text"],
    },
}

RUN_NEXT_CODEX_TASK_SCHEMA = {
    "name": "run_next_codex_task",
    "description": "Run the next queued Codex task, if any.",
    "parameters": {"type": "object", "properties": {}},
}

DELIVER_CODEX_TASK_RESULT_SCHEMA = {
    "name": "deliver_codex_task_result",
    "description": "Deliver a completed queued Codex task result back to its saved Feishu target.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Optional queued task id. If omitted, the newest undelivered completed task is used.",
            }
        },
    },
}

ENSURE_CODEX_WORKER_CRON_SCHEMA = {
    "name": "ensure_codex_worker_cron",
    "description": "Create or reuse the Hermes cron job that drains one Codex queue task per scheduler tick.",
    "parameters": {"type": "object", "properties": {}},
}

CODEX_TASK_STATUS_SCHEMA = {
    "name": "get_codex_task_status",
    "description": "Return queued Codex task status.",
    "parameters": {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    },
}

APPROVE_CODEX_TASK_SCHEMA = {
    "name": "approve_codex_task",
    "description": "Approve a queued write Codex task.",
    "parameters": {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    },
}

MANAGE_CODEX_WORKSPACE_SCHEMA = {
    "name": "manage_codex_workspace",
    "description": "Inspect, remove, archive, quota-check, or conflict-check managed Codex worktrees.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["inspect", "remove", "archive", "quota", "conflicts"]},
            "repo": {"type": "string"},
            "path": {"type": "string"},
            "workspace_id": {"type": "string"},
        },
        "required": ["action"],
    },
}


def _handle_create_codex_task(args: dict, **_: object) -> str:
    from tools.registry import tool_error, tool_result

    try:
        cfg = load_config()
        runner = CodexCliRunner(
            codex_executable=cfg.codex_executable,
            extra_env=cfg.codex_env or {},
            max_output_bytes=cfg.max_output_bytes,
        )
        result = create_codex_task(
            cfg,
            runner=runner,
            repo=args.get("repo"),
            path=args.get("path"),
            mode=str(args.get("mode") or "read"),
            prompt=str(args.get("prompt") or ""),
            workspace_id=args.get("workspace_id"),
            codex_session_id=args.get("codex_session_id"),
            approved=False,
            verify_commands=list(args.get("verify_commands") or []),
            allowed_paths=list(args.get("allowed_paths") or []),
        )
        return tool_result(result)
    except Exception as exc:
        return tool_error(f"create_codex_task failed: {type(exc).__name__}: {exc}")


def _handle_submit_codex_command(args: dict, **_: object) -> str:
    from tools.registry import tool_error, tool_result

    try:
        cfg = load_config()
        parsed = parse_codex_command(str(args.get("text") or ""))
        payload = parsed.to_task_payload()
        payload["verify_commands"] = expand_verify_templates(parsed.verify_commands)
        payload["risk"] = assess_task_risk(
            mode=parsed.mode,
            prompt=parsed.prompt,
            verify_commands=list(payload["verify_commands"]),
            allowed_paths=list(payload.get("allowed_paths") or []),
        )
        queued = _queue(cfg).enqueue(payload)
        return tool_result(queued)
    except Exception as exc:
        return tool_error(f"submit_codex_command failed: {type(exc).__name__}: {exc}")


def _handle_run_next_codex_task(args: dict, **_: object) -> str:
    from tools.registry import tool_error, tool_result

    try:
        cfg = load_config()
        return tool_result(run_next_queue_task(cfg, queue=_queue(cfg)))
    except Exception as exc:
        return tool_error(f"run_next_codex_task failed: {type(exc).__name__}: {exc}")


def _handle_deliver_codex_task_result(args: dict, **_: object) -> str:
    from tools.registry import tool_error, tool_result

    try:
        return tool_result(
            deliver_task_result(
                _queue(load_config()),
                task_id=args.get("task_id"),
            )
        )
    except Exception as exc:
        return tool_error(f"deliver_codex_task_result failed: {type(exc).__name__}: {exc}")


def _handle_ensure_codex_worker_cron(args: dict, **_: object) -> str:
    del args
    from tools.registry import tool_error, tool_result

    try:
        cfg = load_config()
        return tool_result(
            ensure_worker_cron_job(
                name=cfg.worker_cron_name,
                schedule=cfg.worker_cron_schedule,
            )
        )
    except Exception as exc:
        return tool_error(f"ensure_codex_worker_cron failed: {type(exc).__name__}: {exc}")


def _handle_get_codex_task_status(args: dict, **_: object) -> str:
    from tools.registry import tool_error, tool_result

    try:
        return tool_result(_queue(load_config()).get(str(args.get("task_id") or "")))
    except Exception as exc:
        return tool_error(f"get_codex_task_status failed: {type(exc).__name__}: {exc}")


def _handle_approve_codex_task(args: dict, **_: object) -> str:
    from tools.registry import tool_error, tool_result

    try:
        return tool_result(_queue(load_config()).approve(str(args.get("task_id") or "")))
    except Exception as exc:
        return tool_error(f"approve_codex_task failed: {type(exc).__name__}: {exc}")


def _handle_manage_codex_workspace(args: dict, **_: object) -> str:
    from tools.registry import tool_error, tool_result

    try:
        cfg = load_config()
        action = args.get("action")
        if action == "quota":
            return tool_result(
                workspace_quota_report(
                    cfg.worktree_root,
                    max_workspaces=cfg.max_workspaces,
                    max_bytes=cfg.max_worktree_bytes,
                )
            )

        project_path = resolve_target(
            cfg,
            repo=args.get("repo"),
            path=args.get("path"),
            mode="read",
        )
        workspace_id = str(args.get("workspace_id") or "")
        if not workspace_id:
            return tool_error("manage_codex_workspace failed: workspace_id is required for this action")
        worktree_path = cfg.worktree_root.expanduser().resolve() / project_path.name / workspace_id
        if action == "inspect":
            return tool_result(inspect_workspace(worktree_path))
        if action == "remove":
            return tool_result(remove_workspace(project_path, worktree_path))
        if action == "archive":
            archive_root = cfg.worktree_archive_root or (cfg.worktree_root.parent / "worktree_archives")
            return tool_result(archive_workspace(project_path, worktree_path, archive_root))
        if action == "conflicts":
            return tool_result(inspect_workspace_conflicts(worktree_path))
        return tool_error("manage_codex_workspace failed: unsupported action")
    except Exception as exc:
        return tool_error(f"manage_codex_workspace failed: {type(exc).__name__}: {exc}")


def _queue(cfg):
    return FileTaskQueue(cfg.artifact_root.parent / "agent_queue")


def _pre_gateway_dispatch_hook(**kwargs):
    cfg = load_config()
    return handle_pre_gateway_dispatch(
        event=kwargs.get("event"),
        gateway=kwargs.get("gateway"),
        queue=_queue(cfg),
        cfg=cfg,
    )


def _feishu_card_action_response_hook(**kwargs):
    cfg = load_config()
    allowed, error = approval_action_allowed(
        cfg=cfg,
        event=kwargs.get("event"),
    )
    return build_card_action_callback_response(
        action_value=kwargs.get("action_value"),
        operator_name=kwargs.get("operator_name") or kwargs.get("operator_open_id"),
        authorization_error=None if allowed else error,
    )


def _hook_supported(hook_name: str) -> bool:
    try:
        from hermes_cli.plugins import VALID_HOOKS
    except Exception:
        return True
    return hook_name in VALID_HOOKS


def register(ctx) -> None:
    ctx.register_tool(
        name="create_codex_task",
        toolset="hermes_local_agent_gateway",
        schema=CREATE_CODEX_TASK_SCHEMA,
        handler=_handle_create_codex_task,
        description="Create a governed local Codex task with workspace policy and artifact capture.",
        emoji="🧭",
    )
    ctx.register_tool(
        name="submit_codex_command",
        toolset="hermes_local_agent_gateway",
        schema=SUBMIT_CODEX_COMMAND_SCHEMA,
        handler=_handle_submit_codex_command,
        description="Parse and enqueue a Feishu /codex command.",
        emoji="📥",
    )
    ctx.register_tool(
        name="run_next_codex_task",
        toolset="hermes_local_agent_gateway",
        schema=RUN_NEXT_CODEX_TASK_SCHEMA,
        handler=_handle_run_next_codex_task,
        description="Run the next queued Codex task.",
        emoji="▶",
    )
    ctx.register_tool(
        name="deliver_codex_task_result",
        toolset="hermes_local_agent_gateway",
        schema=DELIVER_CODEX_TASK_RESULT_SCHEMA,
        handler=_handle_deliver_codex_task_result,
        description="Deliver a completed Codex task result to its saved Feishu target.",
        emoji="📤",
    )
    ctx.register_tool(
        name="ensure_codex_worker_cron",
        toolset="hermes_local_agent_gateway",
        schema=ENSURE_CODEX_WORKER_CRON_SCHEMA,
        handler=_handle_ensure_codex_worker_cron,
        description="Ensure the real Hermes cron scheduler drains the Codex queue.",
        emoji="⏰",
    )
    ctx.register_tool(
        name="get_codex_task_status",
        toolset="hermes_local_agent_gateway",
        schema=CODEX_TASK_STATUS_SCHEMA,
        handler=_handle_get_codex_task_status,
        description="Get queued Codex task status.",
        emoji="🔎",
    )
    ctx.register_tool(
        name="approve_codex_task",
        toolset="hermes_local_agent_gateway",
        schema=APPROVE_CODEX_TASK_SCHEMA,
        handler=_handle_approve_codex_task,
        description="Approve a queued write Codex task.",
        emoji="✅",
    )
    ctx.register_tool(
        name="manage_codex_workspace",
        toolset="hermes_local_agent_gateway",
        schema=MANAGE_CODEX_WORKSPACE_SCHEMA,
        handler=_handle_manage_codex_workspace,
        description="Inspect or remove managed Codex worktrees.",
        emoji="🧹",
    )
    ctx.register_hook("pre_gateway_dispatch", _pre_gateway_dispatch_hook)
    if _hook_supported("feishu_card_action_response"):
        ctx.register_hook("feishu_card_action_response", _feishu_card_action_response_hook)
