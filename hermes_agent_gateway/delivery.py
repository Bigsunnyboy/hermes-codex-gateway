from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .queue import FileTaskQueue

AdapterSender = Callable[..., Any]
CardUpdater = Callable[..., Any]

FINAL_STATUSES = {"DONE", "FAILED"}


def delivery_target_from_event(*, event: Any, platform: str) -> dict[str, str] | None:
    source = getattr(event, "source", None)
    chat_id = getattr(source, "chat_id", None)
    if not chat_id:
        return None
    target: dict[str, str] = {
        "platform": platform,
        "chat_id": str(chat_id),
    }
    reply_to = getattr(event, "message_id", None)
    if reply_to:
        target["reply_to"] = str(reply_to)
    return target


def deliver_task_result(
    queue: FileTaskQueue,
    *,
    task_id: str | None = None,
    adapter_sender: AdapterSender | None = None,
    card_updater: CardUpdater | None = None,
    tool_sender: Callable[[dict[str, str]], Any] | None = None,
) -> dict[str, Any]:
    record = _select_deliverable(queue, task_id=task_id)
    if record is None:
        return {"status": "NO_DELIVERABLE"}

    queue_task_id = str(record["task_id"])
    previous = record.get("delivery_result") or {}
    if previous.get("status") == "DELIVERED":
        return {
            "status": "ALREADY_DELIVERED",
            "task_id": queue_task_id,
            "target": previous.get("target"),
        }

    payload = record.get("payload") or {}
    target = payload.get("delivery") or {}
    platform = str(target.get("platform") or "").lower()
    chat_id = str(target.get("chat_id") or "")
    if not platform or not chat_id:
        result = _delivery_result("NO_TARGET", queue_task_id, None, {"error": "No delivery target saved."})
        queue.mark_delivery(queue_task_id, result)
        return result

    message = format_task_result(record)
    reply_to = target.get("reply_to")
    metadata = {
        "handled_by": "hermes-agent-gateway",
        "agent_queue_task_id": queue_task_id,
    }
    card_result = update_task_lifecycle_card(
        queue,
        record,
        phase=str(record.get("status") or "UNKNOWN"),
        card_updater=card_updater,
    )
    if _send_succeeded(card_result):
        result = _delivery_result("DELIVERED", queue_task_id, f"{platform}:{chat_id}", card_result)
        result["method"] = "card_update"
        queue.mark_delivery(queue_task_id, result)
        return result

    send_result = _send_with_adapter(
        adapter_sender,
        platform=platform,
        chat_id=chat_id,
        message=message,
        reply_to=reply_to,
        metadata=metadata,
    )
    if not _send_succeeded(send_result):
        send_result = _send_with_tool(
            tool_sender,
            platform=platform,
            chat_id=chat_id,
            message=message,
        )

    status = "DELIVERED" if _send_succeeded(send_result) else "DELIVERY_FAILED"
    result = _delivery_result(status, queue_task_id, f"{platform}:{chat_id}", send_result)
    queue.mark_delivery(queue_task_id, result)
    return result


def update_task_lifecycle_card(
    queue: FileTaskQueue,
    record: dict[str, Any],
    *,
    phase: str,
    card_updater: CardUpdater | None = None,
) -> dict[str, Any]:
    payload = record.get("payload") or {}
    delivery = payload.get("delivery") or {}
    approval_card = delivery.get("approval_card") or {}
    message_id = str(approval_card.get("message_id") or "")
    chat_id = str(approval_card.get("chat_id") or delivery.get("chat_id") or "")
    platform = str(approval_card.get("platform") or delivery.get("platform") or "").lower()
    if not message_id or not chat_id or platform not in {"feishu", "lark"}:
        return {"success": False, "error": "No updatable Feishu approval card saved."}

    card = build_task_lifecycle_card(record, phase=phase)
    update_result = _update_card_with_adapter(
        card_updater,
        platform=platform,
        chat_id=chat_id,
        message_id=message_id,
        card=card,
        metadata={
            "handled_by": "hermes-agent-gateway",
            "agent_queue_task_id": str(record.get("task_id") or ""),
            "phase": phase,
        },
    )
    queue.mark_card_update(
        str(record["task_id"]),
        {
            "phase": phase,
            "message_id": message_id,
            "result": update_result,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return update_result


def build_task_lifecycle_card(record: dict[str, Any], *, phase: str) -> dict[str, Any]:
    payload = record.get("payload") or {}
    result = record.get("result") or {}
    status = str(phase or record.get("status") or result.get("status") or "UNKNOWN").upper()
    queue_task_id = str(record.get("task_id") or "")
    project_path = result.get("project_path") or payload.get("path") or payload.get("repo") or "unknown"
    execution_path = result.get("execution_path") or project_path
    workspace = result.get("workspace_id") or payload.get("workspace_id") or "auto"
    verify_results = result.get("verify_results") or []
    failed_verify = [item for item in verify_results if item.get("returncode") != 0]
    final_text = _extract_final_text(result.get("artifact_dir"))

    template = {
        "RUNNING": "blue",
        "DONE": "green",
        "FAILED": "red",
        "REJECTED": "red",
    }.get(status, "grey")
    title = {
        "RUNNING": "Agent task running",
        "DONE": "Agent task done",
        "FAILED": "Agent task failed",
        "REJECTED": "Agent task rejected",
    }.get(status, f"Agent task {status.lower()}")

    lines = [
        f"**Task:** `{queue_task_id}`",
        f"**Status:** `{status}`",
        f"**Project:** `{project_path}`",
        f"**Execution:** `{execution_path}`",
        f"**Workspace:** `{workspace}`",
    ]
    if "returncode" in result:
        lines.append(f"**Return code:** `{result.get('returncode')}`")
    if verify_results:
        lines.append(f"**Verify:** `{len(verify_results) - len(failed_verify)}/{len(verify_results)} passed`")
    if result.get("error"):
        lines.append(f"**Error:** {result['error']}")
    if final_text and status in {"DONE", "FAILED"}:
        lines.extend(["", "**Final result:**", _clip(final_text, 1200)])
    elif result.get("artifact_dir") and status in {"DONE", "FAILED"}:
        lines.append(f"**Artifacts:** `{result['artifact_dir']}`")

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": [{"tag": "markdown", "content": "\n".join(lines)}],
    }


def format_task_result(record: dict[str, Any]) -> str:
    result = record.get("result") or {}
    payload = record.get("payload") or {}
    status = str(record.get("status") or result.get("status") or "UNKNOWN")
    queue_task_id = str(record.get("task_id") or "")
    project_path = result.get("project_path") or payload.get("path") or payload.get("repo") or "unknown"
    execution_path = result.get("execution_path") or project_path
    final_text = _extract_final_text(result.get("artifact_dir"))
    if final_text and status == "DONE" and result.get("success", True):
        return final_text
    lines = [
        f"Agent task finished: {queue_task_id}",
        f"Status: {status}",
        f"Mode: {payload.get('mode', result.get('mode', 'unknown'))}",
        f"Project: {project_path}",
        f"Execution: {execution_path}",
    ]
    if result.get("workspace_id"):
        lines.append(f"Workspace: {result['workspace_id']}")
    if result.get("agent_session_id"):
        lines.append(f"Session: {result['agent_session_id']}")
    if "returncode" in result:
        lines.append(f"Return code: {result.get('returncode')}")
    if result.get("workspace_changed") is not None:
        lines.append(f"Workspace changed: {bool(result.get('workspace_changed'))}")
    verify_results = result.get("verify_results") or []
    if verify_results:
        failed = [item for item in verify_results if item.get("returncode") != 0]
        lines.append(f"Verify: {len(verify_results) - len(failed)}/{len(verify_results)} passed")
    if result.get("error"):
        lines.append(f"Error: {result['error']}")
    if final_text:
        lines.extend(["", "Final result:", final_text])
    elif result.get("artifact_dir"):
        lines.extend(["", f"Artifacts: {result['artifact_dir']}"])
    return "\n".join(lines)


def _select_deliverable(queue: FileTaskQueue, *, task_id: str | None) -> dict[str, Any] | None:
    if task_id:
        record = queue.get(task_id)
        return record if record.get("status") in FINAL_STATUSES else None
    for record in reversed(queue.list_records()):
        if record.get("status") in FINAL_STATUSES and (record.get("payload") or {}).get("delivery"):
            if (record.get("delivery_result") or {}).get("status") != "DELIVERED":
                return record
    return None


def _send_with_adapter(adapter_sender: AdapterSender | None, **kwargs: Any) -> Any:
    if adapter_sender is not None:
        return adapter_sender(**kwargs)
    try:
        from gateway.config import Platform
        from gateway.run import _gateway_runner_ref
        from model_tools import _run_async

        runner = _gateway_runner_ref()
        if runner is None:
            return {"success": False, "error": "No live gateway runner."}
        platform = Platform(str(kwargs["platform"]))
        adapter = runner.adapters.get(platform)
        if adapter is None:
            return {"success": False, "error": f"No live adapter for {platform.value}."}
        send_result = _run_async(
            adapter.send(
                kwargs["chat_id"],
                kwargs["message"],
                reply_to=kwargs.get("reply_to"),
                metadata=kwargs.get("metadata"),
            )
        )
        if getattr(send_result, "success", False):
            return {"success": True, "message_id": getattr(send_result, "message_id", None)}
        return {"success": False, "error": getattr(send_result, "error", "Adapter send failed.")}
    except Exception as exc:
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}


def _update_card_with_adapter(card_updater: CardUpdater | None, **kwargs: Any) -> Any:
    if card_updater is not None:
        return card_updater(**kwargs)
    try:
        from gateway.config import Platform
        from gateway.run import _gateway_runner_ref
        from model_tools import _run_async

        runner = _gateway_runner_ref()
        if runner is None:
            return {"success": False, "error": "No live gateway runner."}
        platform = Platform(str(kwargs["platform"]))
        adapter = runner.adapters.get(platform)
        if adapter is None:
            return {"success": False, "error": f"No live adapter for {platform.value}."}
        if not hasattr(adapter, "edit_interactive_card"):
            return {"success": False, "error": "Adapter does not support interactive card update."}
        update_result = _run_async(
            adapter.edit_interactive_card(
                kwargs["chat_id"],
                kwargs["message_id"],
                kwargs["card"],
            )
        )
        if getattr(update_result, "success", False):
            return {"success": True, "message_id": getattr(update_result, "message_id", kwargs["message_id"])}
        return {"success": False, "error": getattr(update_result, "error", "Card update failed.")}
    except Exception as exc:
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}


def _send_with_tool(
    tool_sender: Callable[[dict[str, str]], Any] | None,
    *,
    platform: str,
    chat_id: str,
    message: str,
) -> Any:
    args = {
        "action": "send",
        "target": f"{platform}:{chat_id}",
        "message": message,
    }
    try:
        raw = tool_sender(args) if tool_sender else _default_tool_sender(args)
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {"success": False, "raw": raw}
        return raw
    except Exception as exc:
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}


def _default_tool_sender(args: dict[str, str]) -> Any:
    from tools.send_message_tool import send_message_tool

    return send_message_tool(args)


def _send_succeeded(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("success"))
    return bool(getattr(value, "success", False))


def _delivery_result(status: str, task_id: str, target: str | None, send_result: Any) -> dict[str, Any]:
    result = {
        "status": status,
        "task_id": task_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "send_result": send_result,
    }
    if target:
        result["target"] = target
    return result


def _extract_final_text(artifact_dir: Any) -> str:
    if not artifact_dir:
        return ""
    stdout_path = Path(str(artifact_dir)) / "agent_stdout.jsonl"
    candidates: list[str] = []
    try:
        with stdout_path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = _event_text(event)
                if text:
                    candidates.append(text)
    except FileNotFoundError:
        return ""
    if not candidates:
        return ""
    return _clip("\n\n".join(candidates))


def _event_text(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "")
    role = str(event.get("role") or "")
    item = event.get("item")
    if isinstance(item, dict) and str(item.get("type") or "") in {"agent_message", "assistant_message"}:
        return _coerce_text(item.get("message") or item.get("text") or item.get("content"))
    if event_type in {"agent_message", "assistant_message"}:
        return _coerce_text(event.get("message") or event.get("text") or event.get("content"))
    if role == "assistant" or event_type in {"message", "response.output_text", "output_text"}:
        return _coerce_text(event.get("message") or event.get("text") or event.get("content"))
    return ""


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(_coerce_text(item.get("text") or item.get("content")))
            else:
                parts.append(_coerce_text(item))
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        return _coerce_text(value.get("text") or value.get("content"))
    return ""


def _clip(text: str, limit: int = 3000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n... [truncated]"
