from __future__ import annotations

import asyncio
import json
from typing import Any

from .command_parser import parse_codex_command
from .config import GatewayConfig
from .delivery import delivery_target_from_event
from .queue import FileTaskQueue
from .risk_policy import assess_task_risk
from .verify_templates import expand_verify_templates


def build_card_action_callback_response(
    *,
    action_value: Any,
    operator_name: str | None = None,
    authorization_error: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(action_value, dict):
        return None
    action = str(action_value.get("hermes_codex_action") or "").strip().lower()
    if action == "deny":
        action = "reject"
    if action not in {"approve", "reject"}:
        return None
    task_id = str(action_value.get("task_id") or action_value.get("task") or action_value.get("id") or "").strip()
    if not task_id:
        return None
    if authorization_error:
        return {
            "card": _build_approval_denied_card(
                task_id=task_id,
                operator_name=_clean_operator_name(operator_name),
                reason=authorization_error,
            )
        }
    return {
        "card": _build_resolved_approval_card(
            action=action,
            task_id=task_id,
            operator_name=_clean_operator_name(operator_name),
        )
    }


def handle_pre_gateway_dispatch(
    *,
    event: Any,
    queue: FileTaskQueue,
    gateway: Any = None,
    cfg: GatewayConfig | None = None,
) -> dict[str, Any]:
    text = str(getattr(event, "text", "") or "").strip()
    if not (text.startswith("/codex") or text.startswith("/card")):
        return {"action": "allow"}

    source = getattr(event, "source", None)
    platform = _platform_value(getattr(source, "platform", ""))
    if platform not in {"feishu", "lark"}:
        return {"action": "allow"}

    command = _parse_control_command(text) or _parse_card_control_command(text)
    if command:
        return _handle_control_command(
            command=command,
            queue=queue,
            gateway=gateway,
            event=event,
            platform=platform,
            cfg=cfg,
        )

    parsed = parse_codex_command(text)
    verify_commands = expand_verify_templates(parsed.verify_commands)
    payload = parsed.to_task_payload()
    payload["verify_commands"] = verify_commands
    payload["risk"] = assess_task_risk(
        mode=parsed.mode,
        prompt=parsed.prompt,
        verify_commands=verify_commands,
        allowed_paths=list(payload.get("allowed_paths") or []),
    )
    delivery = delivery_target_from_event(event=event, platform=platform)
    if delivery:
        payload["delivery"] = delivery
    queued = queue.enqueue(payload)
    _send_ack(gateway=gateway, event=event, platform=platform, queued=queued, queue=queue)
    return {
        "action": "skip",
        "reason": "codex-command-enqueued",
        "task_id": queued["task_id"],
        "status": queued["status"],
    }


def _parse_control_command(text: str) -> dict[str, str] | None:
    import shlex

    first_line = text.strip().splitlines()[0].strip()
    tokens = shlex.split(first_line)
    if len(tokens) < 2 or tokens[0] != "/codex":
        return None
    action = tokens[1].lower()
    if action == "deny":
        action = "reject"
    if action not in {"approve", "reject", "status"}:
        return None

    task_id = ""
    if len(tokens) >= 3 and "=" not in tokens[2]:
        task_id = tokens[2]
    for token in tokens[2:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key.strip().lower() in {"task", "task_id", "id"}:
            task_id = value.strip()
            break
    return {"action": action, "task_id": task_id}


def _parse_card_control_command(text: str) -> dict[str, str] | None:
    first_line = text.strip().splitlines()[0].strip()
    if not first_line.startswith("/card "):
        return None
    parts = first_line.split(" ", 2)
    if len(parts) < 3:
        return None
    try:
        value = json.loads(parts[2])
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    action = str(value.get("hermes_codex_action") or "").strip().lower()
    if action == "deny":
        action = "reject"
    if action not in {"approve", "reject", "status"}:
        return None
    task_id = str(value.get("task_id") or value.get("task") or value.get("id") or "").strip()
    return {"action": action, "task_id": task_id}


def _handle_control_command(
    *,
    command: dict[str, str],
    queue: FileTaskQueue,
    gateway: Any,
    event: Any,
    platform: str,
    cfg: GatewayConfig,
) -> dict[str, Any]:
    action = command["action"]
    task_id = command["task_id"]
    if not task_id:
        message = f"Codex {action} failed: task id is required.\nUsage: /codex {action} queued_..."
        _send_text(gateway=gateway, event=event, platform=platform, content=message)
        return {"action": "skip", "reason": f"codex-{action}-missing-task-id", "status": "ERROR"}

    try:
        if action == "approve":
            allowed, error = approval_action_allowed(cfg=cfg, event=event)
            if not allowed:
                return _deny_approval_action(
                    action=action,
                    task_id=task_id,
                    error=error,
                    gateway=gateway,
                    event=event,
                    platform=platform,
                )
            record = queue.approve(task_id, approved_by=_source_user_id(event))
        elif action == "reject":
            allowed, error = approval_action_allowed(cfg=cfg, event=event)
            if not allowed:
                return _deny_approval_action(
                    action=action,
                    task_id=task_id,
                    error=error,
                    gateway=gateway,
                    event=event,
                    platform=platform,
                )
            record = queue.reject(task_id, rejected_by=_source_user_id(event))
        else:
            record = queue.get(task_id)
    except Exception as exc:
        message = f"Codex {action} failed: {type(exc).__name__}: {exc}"
        _send_text(gateway=gateway, event=event, platform=platform, content=message)
        return {
            "action": "skip",
            "reason": f"codex-{action}-failed",
            "task_id": task_id,
            "status": "ERROR",
        }

    if action == "approve":
        content = (
            f"Codex task approved: {record['task_id']}\n"
            f"Status: {record['status']}\n"
            "The background worker will run it on the next scheduler tick."
        )
        reason = "codex-task-approved"
    elif action == "reject":
        content = f"Codex task rejected: {record['task_id']}\nStatus: {record['status']}"
        reason = "codex-task-rejected"
    else:
        content = f"Codex task status: {record['task_id']}\nStatus: {record['status']}"
        reason = "codex-task-status"
    if action in {"approve", "reject"}:
        _update_approval_card_state(
            gateway=gateway,
            event=event,
            platform=platform,
            record=record,
            action=action,
        )
    _send_text(gateway=gateway, event=event, platform=platform, content=content)
    return {
        "action": "skip",
        "reason": reason,
        "task_id": record["task_id"],
        "status": record["status"],
    }


def _deny_approval_action(
    *,
    action: str,
    task_id: str,
    error: str,
    gateway: Any,
    event: Any,
    platform: str,
) -> dict[str, Any]:
    content = f"Codex {action} denied: {task_id}\nReason: {error}"
    _send_text(gateway=gateway, event=event, platform=platform, content=content)
    return {
        "action": "skip",
        "reason": f"codex-{action}-unauthorized",
        "task_id": task_id,
        "status": "UNAUTHORIZED",
    }


def _platform_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").lower()


def _send_ack(
    *,
    gateway: Any,
    event: Any,
    platform: str,
    queued: dict[str, Any],
    queue: FileTaskQueue,
) -> None:
    if gateway is None:
        return
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = _adapter_for_platform(adapters, platform)
    if adapter is None:
        return
    source = getattr(event, "source", None)
    chat_id = getattr(source, "chat_id", None)
    if not chat_id:
        return
    risk = (queued.get("payload") or {}).get("risk") or {}
    if queued.get("status") == "APPROVAL_REQUIRED" and _send_approval_card(
        gateway=gateway,
        event=event,
        platform=platform,
        queued=queued,
        queue=queue,
    ):
        return
    content = (
        f"Codex task queued: {queued['task_id']}\n"
        f"Status: {queued['status']}\n"
        f"Risk: {risk.get('level', 'unknown')}"
    )
    _send_text(gateway=gateway, event=event, platform=platform, content=content)


def _send_approval_card(
    *,
    gateway: Any,
    event: Any,
    platform: str,
    queued: dict[str, Any],
    queue: FileTaskQueue | None = None,
) -> bool:
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = _adapter_for_platform(adapters, platform)
    if adapter is None or not hasattr(adapter, "_feishu_send_with_retry"):
        return False
    source = getattr(event, "source", None)
    chat_id = getattr(source, "chat_id", None)
    if not chat_id:
        return False
    card = _build_approval_card(queued)
    coroutine = _send_interactive_card(
        adapter=adapter,
        chat_id=str(chat_id),
        card=card,
        reply_to=getattr(event, "message_id", None),
        metadata={
            "handled_by": "hermes-codex-gateway",
            "codex_queue_task_id": str(queued["task_id"]),
        },
        queue=queue,
        task_id=str(queued["task_id"]),
        platform=platform,
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    loop.create_task(coroutine)
    return True


async def _send_interactive_card(
    *,
    adapter: Any,
    chat_id: str,
    card: dict[str, Any],
    reply_to: str | None,
    metadata: dict[str, Any],
    queue: FileTaskQueue | None = None,
    task_id: str | None = None,
    platform: str = "feishu",
) -> None:
    response = await adapter._feishu_send_with_retry(
        chat_id=chat_id,
        msg_type="interactive",
        payload=json.dumps(card, ensure_ascii=False),
        reply_to=reply_to,
        metadata=metadata,
    )
    message_id = _response_message_id(response)
    if queue is not None and task_id and message_id:
        queue.mark_approval_card(
            task_id,
            {
                "platform": platform,
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_to": reply_to,
                "kind": "codex_write_approval",
            },
        )


def _build_approval_card(queued: dict[str, Any]) -> dict[str, Any]:
    payload = queued.get("payload") or {}
    risk = payload.get("risk") if isinstance(payload.get("risk"), dict) else {}
    task_id = str(queued["task_id"])
    target = payload.get("path") or payload.get("repo") or "unknown"
    verify = ", ".join(str(item) for item in payload.get("verify_commands") or []) or "none"
    allowed = ", ".join(str(item) for item in payload.get("allowed_paths") or []) or "not set"
    workspace = payload.get("workspace_id") or "auto"
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "orange",
            "title": {"tag": "plain_text", "content": "Codex write approval required"},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": "\n".join(
                    [
                        f"**Task:** `{task_id}`",
                        f"**Target:** `{target}`",
                        f"**Workspace:** `{workspace}`",
                        f"**Risk:** `{risk.get('level', 'unknown')}`",
                        f"**Verify:** `{verify}`",
                        f"**Allow:** `{allowed}`",
                    ]
                ),
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "批准执行"},
                        "type": "primary",
                        "value": {"hermes_codex_action": "approve", "task_id": task_id},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "拒绝"},
                        "type": "danger",
                        "value": {"hermes_codex_action": "reject", "task_id": task_id},
                    },
                ],
            },
        ],
    }


def _build_resolved_approval_card(*, action: str, task_id: str, operator_name: str | None = None) -> dict[str, Any]:
    approved = action == "approve"
    title = "Codex task approved" if approved else "Codex task rejected"
    status = "QUEUED" if approved else "REJECTED"
    lines = [
        f"**Task:** `{task_id}`",
        f"**Status:** `{status}`",
    ]
    if operator_name:
        lines.append(f"**Operator:** {operator_name}")
    if approved:
        lines.append("The background worker will run it on the next scheduler tick.")
    else:
        lines.append("This task will not run.")
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "green" if approved else "red",
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": "\n".join(lines),
            },
        ],
    }


def _build_approval_denied_card(*, task_id: str, operator_name: str | None, reason: str) -> dict[str, Any]:
    lines = [
        f"**Task:** `{task_id}`",
        "**Status:** `UNAUTHORIZED`",
        f"**Reason:** {reason}",
    ]
    if operator_name:
        lines.append(f"**Operator:** {operator_name}")
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "red",
            "title": {"tag": "plain_text", "content": "Codex approval denied"},
        },
        "elements": [
            {
                "tag": "markdown",
                "content": "\n".join(lines),
            },
        ],
    }


def _send_text(*, gateway: Any, event: Any, platform: str, content: str) -> None:
    if gateway is None:
        return
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = _adapter_for_platform(adapters, platform)
    if adapter is None:
        return
    source = getattr(event, "source", None)
    chat_id = getattr(source, "chat_id", None)
    if not chat_id:
        return
    coroutine = adapter.send(
        chat_id,
        content,
        reply_to=getattr(event, "message_id", None),
        metadata={"handled_by": "hermes-codex-gateway"},
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    loop.create_task(coroutine)


def approval_action_allowed(*, cfg: GatewayConfig | None, event: Any) -> tuple[bool, str]:
    if cfg is None:
        return True, ""
    source = getattr(event, "source", None)
    user_id = _source_user_id(event) or ""
    chat_id = str(getattr(source, "chat_id", "") or "")
    allowed_users = {str(item).strip() for item in (cfg.approval_allowed_user_ids or []) if str(item).strip()}
    allowed_chats = {str(item).strip() for item in (cfg.approval_allowed_chat_ids or []) if str(item).strip()}
    if allowed_users and user_id not in allowed_users:
        return False, "operator is not in approval_allowed_user_ids"
    if allowed_chats and chat_id not in allowed_chats:
        return False, "chat is not in approval_allowed_chat_ids"
    return True, ""


def _update_approval_card_state(
    *,
    gateway: Any,
    event: Any,
    platform: str,
    record: dict[str, Any],
    action: str,
) -> None:
    if gateway is None:
        return
    delivery = (record.get("payload") or {}).get("delivery") or {}
    approval_card = delivery.get("approval_card") or {}
    message_id = str(approval_card.get("message_id") or "")
    chat_id = str(approval_card.get("chat_id") or delivery.get("chat_id") or "")
    if not message_id or not chat_id:
        return
    adapters = getattr(gateway, "adapters", {}) or {}
    adapter = _adapter_for_platform(adapters, platform)
    if adapter is None or not hasattr(adapter, "edit_interactive_card"):
        return
    coroutine = adapter.edit_interactive_card(
        chat_id,
        message_id,
        _build_resolved_approval_card(
            action=action,
            task_id=str(record["task_id"]),
            operator_name=_source_user_display_name(event),
        ),
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    loop.create_task(coroutine)


def _adapter_for_platform(adapters: dict[Any, Any], platform: str) -> Any:
    adapter = adapters.get(platform)
    if adapter is not None:
        return adapter
    for key, candidate in adapters.items():
        if _platform_value(key) == platform:
            return candidate
    return None


def _response_message_id(response: Any) -> str:
    data = getattr(response, "data", None)
    for container in (data, response):
        for attr in ("message_id", "messageId"):
            value = getattr(container, attr, None)
            if value:
                return str(value)
        if isinstance(container, dict):
            value = container.get("message_id") or container.get("messageId")
            if value:
                return str(value)
    return ""


def _source_user_id(event: Any) -> str | None:
    source = getattr(event, "source", None)
    for attr in ("user_id", "user_id_alt", "open_id"):
        value = getattr(source, attr, None)
        if value:
            return str(value)
    return None


def _source_user_display_name(event: Any) -> str | None:
    source = getattr(event, "source", None)
    for attr in ("user_name", "display_name", "name"):
        value = getattr(source, attr, None)
        cleaned = _clean_operator_name(value)
        if cleaned:
            return cleaned
    return _clean_operator_name(_source_user_id(event))


def _clean_operator_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.startswith(("ou_", "u_", "on_")):
        return None
    return text
