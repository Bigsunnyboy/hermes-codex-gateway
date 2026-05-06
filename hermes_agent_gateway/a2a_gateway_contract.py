from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .runners.registry import enabled_runner_ids, get_runner_definition


@dataclass(frozen=True)
class RunnerCapabilityView:
    id: str
    supports_read: bool
    supports_write: bool
    supports_resume: bool
    supports_structured_output: bool
    supports_permission_mode: bool
    dangerous_modes_disabled: bool


@dataclass(frozen=True)
class ProtocolCapabilityPosture:
    streaming: bool = False
    subscription_updates: bool = False
    push_notifications: bool = False
    extended_descriptor: bool = False
    signed_descriptor: bool = False
    public_endpoints: bool = False


@dataclass(frozen=True)
class GatewayGovernanceMetadata:
    approval_required_for_write: bool
    risk_policy: bool
    path_guard: bool
    verification: bool
    artifact_capture: bool
    audit: bool


@dataclass(frozen=True)
class GatewaySkillView:
    id: str
    name: str
    description: str
    requires_approval: bool = False


@dataclass(frozen=True)
class GatewayAgentDescriptor:
    name: str
    enabled_runners: tuple[str, ...]
    runner_capabilities: tuple[RunnerCapabilityView, ...]
    skills: tuple[GatewaySkillView, ...]
    protocol_capabilities: ProtocolCapabilityPosture
    governance: GatewayGovernanceMetadata


@dataclass(frozen=True)
class GatewayActorRef:
    source: str
    actor_id: str
    display_name: str | None = None


@dataclass(frozen=True)
class GatewayMessageEnvelope:
    runner: str
    mode: str
    prompt: str
    repo: str | None = None
    path: str | None = None
    workspace_id: str | None = None
    agent_session_id: str | None = None
    verify_commands: tuple[str, ...] = ()
    allowed_paths: tuple[str, ...] = ()
    actor: GatewayActorRef | None = None


@dataclass(frozen=True)
class GatewayTaskStateView:
    state: str
    terminal: bool
    requires_future_binding_decision: bool = False
    candidate_protocol_states: tuple[str, ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class GatewayArtifactView:
    category: str
    payload: Any


EVENT_SEMANTICS: tuple[str, ...] = (
    "task_submitted",
    "approval_required",
    "task_rejected",
    "task_working",
    "task_blocked",
    "artifact_available",
    "task_completed",
    "task_failed",
)

_SENSITIVE_PATH_KEYS = {
    "project_path",
    "execution_path",
    "artifact_dir",
    "stdout_path",
    "stderr_path",
}
_ABSOLUTE_PATH_PATTERN = re.compile(r"(?<![\w.])/(?:[^\s'\"<>|;:]+/?)+")

TEXT_PREVIEW_LIMIT_BYTES = 16 * 1024
DIFF_PREVIEW_LIMIT_BYTES = 64 * 1024
SUMMARY_PREVIEW_LIMIT_BYTES = 8 * 1024

_TEXT_ARTIFACTS = {
    "agent_stdout.jsonl": ("stdout", TEXT_PREVIEW_LIMIT_BYTES),
    "agent_stderr.log": ("stderr", TEXT_PREVIEW_LIMIT_BYTES),
    "before_status.txt": ("before_status", TEXT_PREVIEW_LIMIT_BYTES),
    "after_status.txt": ("after_status", TEXT_PREVIEW_LIMIT_BYTES),
    "before_diff_stat.txt": ("before_diff_stat", DIFF_PREVIEW_LIMIT_BYTES),
    "after_diff_stat.txt": ("after_diff_stat", DIFF_PREVIEW_LIMIT_BYTES),
    "before_diff.txt": ("before_diff", DIFF_PREVIEW_LIMIT_BYTES),
    "after_diff.txt": ("after_diff", DIFF_PREVIEW_LIMIT_BYTES),
}

_PRIVATE_RECORD_KEYS = {
    "delivery",
    "delivery_result",
    "approval" + "_card",
    "card_updates",
}


def build_gateway_agent_descriptor() -> GatewayAgentDescriptor:
    runner_views = tuple(_runner_capability_view(runner_id) for runner_id in enabled_runner_ids())
    return GatewayAgentDescriptor(
        name="Hermes Agent Gateway",
        enabled_runners=tuple(view.id for view in runner_views),
        runner_capabilities=runner_views,
        skills=_skill_views(runner_views),
        protocol_capabilities=ProtocolCapabilityPosture(),
        governance=GatewayGovernanceMetadata(
            approval_required_for_write=True,
            risk_policy=True,
            path_guard=True,
            verification=True,
            artifact_capture=True,
            audit=True,
        ),
    )


def normalize_message_envelope(payload: Mapping[str, Any]) -> GatewayMessageEnvelope:
    runner = _required_text(payload, "runner")
    get_runner_definition(runner)

    mode = _required_text(payload, "mode").lower()
    if mode not in {"read", "write"}:
        raise ValueError("mode must be read or write")

    prompt = _required_text(payload, "prompt")
    actor = _actor_ref(payload.get("actor"))

    return GatewayMessageEnvelope(
        runner=runner.strip().lower(),
        mode=mode,
        prompt=prompt,
        repo=_optional_text(payload.get("repo")),
        path=_optional_text(payload.get("path")),
        workspace_id=_optional_text(payload.get("workspace_id")),
        agent_session_id=_optional_text(payload.get("agent_session_id")),
        verify_commands=_text_tuple(payload.get("verify_commands"), "verify_commands"),
        allowed_paths=_text_tuple(payload.get("allowed_paths"), "allowed_paths"),
        actor=actor,
    )


def gateway_task_state_view(record: Mapping[str, Any]) -> GatewayTaskStateView:
    status = str(record.get("status") or "").upper()
    result = record.get("result") if isinstance(record.get("result"), Mapping) else {}

    if status == "QUEUED":
        return GatewayTaskStateView("submitted", terminal=False)
    if status == "RUNNING":
        return GatewayTaskStateView("working", terminal=False)
    if status == "APPROVAL_REQUIRED":
        return GatewayTaskStateView(
            "input-required",
            terminal=False,
            requires_future_binding_decision=True,
            candidate_protocol_states=("input-required",),
            reason="gateway approval required",
        )
    if status == "DONE" and result.get("success", True) is True:
        return GatewayTaskStateView("completed", terminal=True)
    if status == "FAILED" or (status == "DONE" and result.get("success") is False):
        return GatewayTaskStateView("failed", terminal=True, reason=_failure_reason(result))
    if status == "REJECTED":
        return GatewayTaskStateView(
            "rejected",
            terminal=True,
            requires_future_binding_decision=True,
            candidate_protocol_states=("rejected",),
            reason="approval rejected",
        )
    if status == "BLOCKED":
        return GatewayTaskStateView(
            "blocked",
            terminal=True,
            requires_future_binding_decision=True,
            candidate_protocol_states=("rejected", "failed"),
            reason=_risk_reason(record),
        )

    raise ValueError(f"unknown gateway task status: {status or '<missing>'}")


def gateway_message_payload(envelope: GatewayMessageEnvelope) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "runner": envelope.runner,
        "mode": envelope.mode,
        "prompt": envelope.prompt,
        "verify_commands": list(envelope.verify_commands),
        "allowed_paths": list(envelope.allowed_paths),
    }
    for field_name in ("repo", "path", "workspace_id", "agent_session_id"):
        value = getattr(envelope, field_name)
        if value is not None:
            payload[field_name] = value
    return payload


def sanitize_task_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return _sanitize_mapping(record)


def artifact_views(record: Mapping[str, Any]) -> tuple[GatewayArtifactView, ...]:
    views = [
        GatewayArtifactView("task_record", sanitize_task_record(record)),
    ]

    for category, key in (
        ("summary", "status"),
        ("stdout", "stdout"),
        ("stderr", "stderr"),
        ("diff", "diff"),
        ("verification", "verify_results"),
        ("audit", "risk"),
    ):
        value = record.get(key)
        if value not in (None, "", [], {}):
            views.append(GatewayArtifactView(category, _sanitize_value(value)))

    return tuple(views)


def artifact_manifest(artifact_dir: str | Path) -> dict[str, Any]:
    root = Path(artifact_dir).expanduser().resolve()
    items: dict[str, Any] = {}

    task_record = _read_json_artifact(root, "task.json", error_category="task_record_error")
    if task_record is not None:
        if isinstance(task_record, Mapping) and task_record.get("category") == "task_record_error":
            items["task_record_error"] = task_record
        elif isinstance(task_record, Mapping):
            items["task_record"] = {
                "category": "task_record",
                "payload": _sanitize_for_view(task_record),
            }
        else:
            items["task_record_error"] = task_record

    for basename, (category, limit_bytes) in _TEXT_ARTIFACTS.items():
        preview = _read_text_artifact(root, basename, limit_bytes)
        if preview is not None:
            items[category] = preview

    verification = _verification_artifact(root)
    if verification is not None:
        if verification.get("category") == "verification":
            items["verification"] = verification
        else:
            items["verification_error"] = verification

    return {
        "artifact_dir": "<redacted-path>",
        "items": items,
    }


def gateway_task_record_view(record: Mapping[str, Any]) -> dict[str, Any]:
    task_id = _required_text(record, "task_id")
    status = _required_text(record, "status").upper()
    state = _queue_task_state_view(record)
    payload = _public_record_mapping(record.get("payload"))
    result = _public_record_mapping(record.get("result"))
    artifact_dir = _artifact_dir_from_result(record.get("result"))
    artifacts = artifact_manifest(artifact_dir) if artifact_dir else {"items": {}}
    task_record = _task_record_payload(artifacts)
    execution_task_id = _execution_task_id(record.get("result"), task_record)
    mismatches = _status_mismatches(status, record.get("result"), task_record)

    view: dict[str, Any] = {
        "task_id": task_id,
        "status": status,
        "state": {
            "state": state.state,
            "terminal": state.terminal,
            "requires_future_binding_decision": state.requires_future_binding_decision,
            "candidate_protocol_states": list(state.candidate_protocol_states),
            "reason": state.reason,
        },
        "approved": bool(record.get("approved", False)),
        "payload": payload,
        "result": result,
        "artifacts": artifacts,
        "mismatches": mismatches,
    }

    for key in ("created_at", "updated_at"):
        value = record.get(key)
        if isinstance(value, str):
            view[key] = _sanitize_text(value)

    approval = record.get("approval")
    if isinstance(approval, Mapping):
        view["approval"] = _sanitize_for_view(approval)
    if execution_task_id:
        view["execution_task_id"] = execution_task_id

    return view


def _runner_capability_view(runner_id: str) -> RunnerCapabilityView:
    definition = get_runner_definition(runner_id)
    capabilities = definition.capabilities
    return RunnerCapabilityView(
        id=definition.id,
        supports_read=capabilities.supports_read,
        supports_write=capabilities.supports_write,
        supports_resume=capabilities.supports_resume,
        supports_structured_output=capabilities.supports_json_output,
        supports_permission_mode=capabilities.supports_permission_mode,
        dangerous_modes_disabled=capabilities.dangerous_modes_disabled,
    )


def _skill_views(runners: tuple[RunnerCapabilityView, ...]) -> tuple[GatewaySkillView, ...]:
    skills: list[GatewaySkillView] = []
    if any(runner.supports_read for runner in runners):
        skills.append(
            GatewaySkillView(
                id="read_task",
                name="Read task",
                description="Run a read-only governed agent task.",
            )
        )
    if any(runner.supports_write for runner in runners):
        skills.append(
            GatewaySkillView(
                id="approved_write_task",
                name="Approved write task",
                description="Run a governed write task after approval and policy checks.",
                requires_approval=True,
            )
        )
    if any(runner.supports_resume for runner in runners):
        skills.append(
            GatewaySkillView(
                id="resume_task",
                name="Resume task",
                description="Continue a task when the selected runner supports session resume.",
            )
        )
    return tuple(skills)


def _queue_task_state_view(record: Mapping[str, Any]) -> GatewayTaskStateView:
    status = str(record.get("status") or "").upper()
    if status == "DONE":
        return GatewayTaskStateView("completed", terminal=True)
    if status == "FAILED":
        result = record.get("result") if isinstance(record.get("result"), Mapping) else {}
        return GatewayTaskStateView("failed", terminal=True, reason=_failure_reason(result))
    return gateway_task_state_view({**record, "result": {}})


def _public_record_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    public = {
        key: item
        for key, item in value.items()
        if key not in _PRIVATE_RECORD_KEYS
    }
    return _sanitize_for_view(public)


def _artifact_dir_from_result(value: Any) -> Path | None:
    if not isinstance(value, Mapping):
        return None
    artifact_dir = value.get("artifact_dir")
    if not isinstance(artifact_dir, str) or not artifact_dir.strip():
        return None
    return Path(artifact_dir)


def _task_record_payload(artifacts: Mapping[str, Any]) -> Mapping[str, Any]:
    items = artifacts.get("items") if isinstance(artifacts.get("items"), Mapping) else {}
    task_record = items.get("task_record") if isinstance(items.get("task_record"), Mapping) else {}
    payload = task_record.get("payload") if isinstance(task_record.get("payload"), Mapping) else {}
    return payload


def _execution_task_id(result: Any, task_record: Mapping[str, Any]) -> str | None:
    if isinstance(result, Mapping):
        task_id = result.get("task_id")
        if isinstance(task_id, str) and task_id.strip():
            return task_id.strip()
    task_id = task_record.get("task_id")
    if isinstance(task_id, str) and task_id.strip():
        return task_id.strip()
    return None


def _status_mismatches(
    queue_status: str,
    result: Any,
    task_record: Mapping[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    if isinstance(result, Mapping):
        result_status = result.get("status")
        if isinstance(result_status, str) and result_status.upper() != queue_status:
            mismatches.append("result.status differs from queue status")
    task_status = task_record.get("status")
    if isinstance(task_status, str) and task_status.upper() != queue_status:
        mismatches.append("task_record.status differs from queue status")
    return mismatches


def _read_json_artifact(
    root: Path,
    basename: str,
    *,
    error_category: str,
) -> dict[str, Any] | list[Any] | None:
    path = _contained_artifact_path(root, basename)
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "category": error_category,
            "payload": {
                "error": "invalid json",
                "path": _sanitize_text(str(path)),
            },
        }


def _read_text_artifact(root: Path, basename: str, limit_bytes: int) -> dict[str, Any] | None:
    path = _contained_artifact_path(root, basename)
    if path is None or not path.exists():
        return None
    return _preview_file(path, limit_bytes)


def _verification_artifact(root: Path) -> dict[str, Any] | None:
    raw_results = _read_json_artifact(
        root,
        "verify_results.json",
        error_category="verification_error",
    )
    if raw_results is None:
        return None
    if not isinstance(raw_results, list):
        return raw_results

    results = _sanitize_for_view(raw_results)
    logs = []
    for index, raw_result in enumerate(raw_results, start=1):
        if not isinstance(raw_result, Mapping):
            continue
        log_entry: dict[str, Any] = {"index": index}
        if raw_result.get("stdout"):
            stdout = _read_text_artifact(root, f"verify_{index}_stdout.log", TEXT_PREVIEW_LIMIT_BYTES)
            if stdout is not None:
                log_entry["stdout"] = stdout
        if raw_result.get("stderr"):
            stderr = _read_text_artifact(root, f"verify_{index}_stderr.log", TEXT_PREVIEW_LIMIT_BYTES)
            if stderr is not None:
                log_entry["stderr"] = stderr
        if len(log_entry) > 1:
            logs.append(log_entry)

    return {
        "category": "verification",
        "payload": {
            "results": results,
            "logs": logs,
        },
    }


def _contained_artifact_path(root: Path, basename: str) -> Path | None:
    if "/" in basename or "\\" in basename or basename in {"", ".", ".."}:
        return None
    try:
        path = (root / basename).resolve(strict=True)
    except FileNotFoundError:
        return None
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


def _preview_file(path: Path, limit_bytes: int) -> dict[str, Any]:
    with path.open("rb") as file:
        raw = file.read(limit_bytes + 1)
    truncated = len(raw) > limit_bytes
    preview = raw[:limit_bytes]
    return {
        "content": _sanitize_text(preview.decode("utf-8", errors="replace")),
        "truncated": truncated,
        "bytes_read": len(preview),
        "limit_bytes": limit_bytes,
    }


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional text fields must be strings")
    stripped = value.strip()
    return stripped or None


def _text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")
    result = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must be a list of strings")
        stripped = item.strip()
        if stripped:
            result.append(stripped)
    return tuple(result)


def _actor_ref(value: Any) -> GatewayActorRef | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("actor must be an object")
    actor_id = value.get("actor_id")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise ValueError("actor.actor_id is required")
    source = value.get("source", "a2a")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("actor.source must be a string")
    if source.strip().lower() != "a2a":
        raise ValueError("actor.source must be a2a")
    display_name = value.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        raise ValueError("actor.display_name must be a string")
    return GatewayActorRef(
        source=source.strip().lower(),
        actor_id=actor_id.strip(),
        display_name=(
            display_name.strip()
            if isinstance(display_name, str) and display_name.strip()
            else None
        ),
    )


def _failure_reason(result: Mapping[str, Any]) -> str | None:
    error = result.get("error")
    if isinstance(error, str) and error:
        return error
    if result.get("workspace_changed"):
        return "workspace changed"
    verify_results = result.get("verify_results")
    if isinstance(verify_results, list) and any(
        isinstance(item, Mapping) and item.get("returncode") not in (0, None)
        for item in verify_results
    ):
        return "verification failed"
    return None


def _risk_reason(record: Mapping[str, Any]) -> str | None:
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
    risk = payload.get("risk") if isinstance(payload.get("risk"), Mapping) else {}
    reasons = risk.get("reasons")
    if isinstance(reasons, list) and reasons:
        return "; ".join(str(reason) for reason in reasons)
    return "risk policy blocked execution"


def _sanitize_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _SENSITIVE_PATH_KEYS:
            sanitized[key] = "<redacted-path>"
            continue
        sanitized[key] = _sanitize_value(value)
    return sanitized


def _sanitize_for_view(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key in _SENSITIVE_PATH_KEYS:
                sanitized[key] = "<redacted-path>"
            elif key in {"prompt", "error"} and isinstance(item, str):
                sanitized[key] = _preview_text(item, SUMMARY_PREVIEW_LIMIT_BYTES)
            else:
                sanitized[key] = _sanitize_for_view(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_for_view(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_for_view(item) for item in value)
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _preview_text(value: str, limit_bytes: int) -> dict[str, Any]:
    raw = value.encode("utf-8")
    preview = raw[:limit_bytes]
    return {
        "content": _sanitize_text(preview.decode("utf-8", errors="replace")),
        "truncated": len(raw) > limit_bytes,
        "bytes_read": len(preview),
        "limit_bytes": limit_bytes,
    }


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _sanitize_text(value: str) -> str:
    return _ABSOLUTE_PATH_PATTERN.sub("<redacted-path>", value)
