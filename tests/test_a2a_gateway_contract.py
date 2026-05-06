import pytest

from hermes_agent_gateway.a2a_gateway_contract import (
    EVENT_SEMANTICS,
    artifact_views,
    build_gateway_agent_descriptor,
    gateway_message_payload,
    gateway_task_state_view,
    normalize_message_envelope,
    sanitize_task_record,
)


def test_descriptor_uses_enabled_runner_truth_without_protocol_claims() -> None:
    descriptor = build_gateway_agent_descriptor()

    assert descriptor.enabled_runners == ("codex",)
    assert {runner.id for runner in descriptor.runner_capabilities} == {"codex"}
    assert {"claude-code", "qoder", "deepseek-tui"}.isdisjoint(descriptor.enabled_runners)
    assert descriptor.protocol_capabilities.streaming is False
    assert descriptor.protocol_capabilities.subscription_updates is False
    assert descriptor.protocol_capabilities.push_notifications is False
    assert descriptor.protocol_capabilities.public_endpoints is False
    assert descriptor.governance.approval_required_for_write is True
    assert descriptor.governance.path_guard is True


def test_descriptor_skills_are_gateway_neutral_and_capability_driven() -> None:
    descriptor = build_gateway_agent_descriptor()

    skill_ids = {skill.id for skill in descriptor.skills}

    assert skill_ids == {"read_task", "approved_write_task", "resume_task"}
    assert all("codex" not in skill.name.lower() for skill in descriptor.skills)
    assert any(skill.id == "approved_write_task" and skill.requires_approval for skill in descriptor.skills)


def test_message_envelope_requires_enabled_runner_and_preserves_gateway_payload() -> None:
    envelope = normalize_message_envelope(
        {
            "runner": " Codex ",
            "repo": "example",
            "path": "src",
            "mode": "read",
            "workspace_id": "inspect",
            "agent_session_id": "session-1",
            "verify_commands": ["pytest tests/test_example.py"],
            "allowed_paths": ["src/example.py"],
            "prompt": "Inspect only.",
            "actor": {"source": "a2a", "actor_id": "user-1", "display_name": "User One"},
        }
    )

    assert envelope.runner == "codex"
    assert envelope.actor is not None
    assert envelope.actor.source == "a2a"
    assert gateway_message_payload(envelope) == {
        "runner": "codex",
        "repo": "example",
        "path": "src",
        "mode": "read",
        "workspace_id": "inspect",
        "agent_session_id": "session-1",
        "verify_commands": ["pytest tests/test_example.py"],
        "allowed_paths": ["src/example.py"],
        "prompt": "Inspect only.",
    }


def test_message_envelope_rejects_reserved_runner_before_queueing() -> None:
    with pytest.raises(ValueError, match="enabled runner"):
        normalize_message_envelope({"runner": "qoder", "mode": "read", "prompt": "Inspect."})


def test_message_envelope_rejects_invalid_mode_and_unsupported_shapes() -> None:
    for payload in (
        {"runner": "codex", "mode": "admin", "prompt": "Inspect."},
        {"runner": "codex", "mode": "read", "prompt": "Inspect.", "verify_commands": "pytest"},
        {"runner": "codex", "mode": "read", "prompt": "Inspect.", "actor": {"source": "a2a"}},
        {
            "runner": "codex",
            "mode": "read",
            "prompt": "Inspect.",
            "actor": {"source": "feishu", "actor_id": "user-1"},
        },
    ):
        with pytest.raises(ValueError):
            normalize_message_envelope(payload)


def test_task_status_semantics_cover_current_queue_states() -> None:
    cases = {
        "QUEUED": ("submitted", False, False),
        "RUNNING": ("working", False, False),
        "APPROVAL_REQUIRED": ("input-required", False, True),
        "DONE": ("completed", True, False),
        "FAILED": ("failed", True, False),
        "REJECTED": ("rejected", True, True),
        "BLOCKED": ("blocked", True, True),
    }

    for status, expected in cases.items():
        view = gateway_task_state_view({"status": status, "payload": {"risk": {"reasons": ["denied"]}}})
        assert (view.state, view.terminal, view.requires_future_binding_decision) == expected


def test_task_status_failed_done_and_unknown_status_fail_closed() -> None:
    failed_done = gateway_task_state_view(
        {"status": "DONE", "result": {"success": False, "workspace_changed": True}}
    )

    assert failed_done.state == "failed"
    assert failed_done.reason == "workspace changed"

    with pytest.raises(ValueError, match="unknown gateway task status"):
        gateway_task_state_view({"status": "MYSTERY"})


def test_blocked_status_preserves_risk_reason_without_wire_state_commitment() -> None:
    view = gateway_task_state_view(
        {
            "status": "BLOCKED",
            "payload": {"risk": {"reasons": ["critical path", "secret file"]}},
        }
    )

    assert view.state == "blocked"
    assert view.candidate_protocol_states == ("rejected", "failed")
    assert view.reason == "critical path; secret file"


def test_task_record_sanitization_removes_private_paths_and_command_paths() -> None:
    sanitized = sanitize_task_record(
        {
            "project_path": "/home/projects/repo",
            "execution_path": "/tmp/worktree/repo",
            "artifact_dir": "/var/artifacts/task",
            "command": ["/usr/local/bin/codex", "exec", "--cd", "/home/projects/repo", "prompt"],
            "error": "failed at /home/projects/repo/app.py after opening /usr/local/bin/codex",
            "nested": {"stderr_path": "/tmp/artifacts/agent_stderr.log"},
            "prompt": "Inspect only.",
        }
    )

    assert sanitized["project_path"] == "<redacted-path>"
    assert sanitized["execution_path"] == "<redacted-path>"
    assert sanitized["artifact_dir"] == "<redacted-path>"
    assert sanitized["command"] == ["<redacted-path>", "exec", "--cd", "<redacted-path>", "prompt"]
    assert sanitized["error"] == "failed at <redacted-path> after opening <redacted-path>"
    assert sanitized["nested"]["stderr_path"] == "<redacted-path>"
    assert sanitized["prompt"] == "Inspect only."


def test_artifact_views_are_bounded_to_gateway_categories() -> None:
    views = artifact_views(
        {
            "status": "DONE",
            "stdout": "ok from /home/projects/repo",
            "stderr": "",
            "diff": "diff --git",
            "verify_results": [{"command": "pytest", "returncode": 0}],
            "risk": {"level": "low"},
            "project_path": "/home/projects/repo",
        }
    )

    categories = {view.category for view in views}

    assert categories == {"task_record", "summary", "stdout", "diff", "verification", "audit"}
    task_record = next(view.payload for view in views if view.category == "task_record")
    assert task_record["project_path"] == "<redacted-path>"
    stdout = next(view.payload for view in views if view.category == "stdout")
    assert stdout == "ok from <redacted-path>"


def test_event_semantics_are_inert_planning_vocabulary() -> None:
    assert EVENT_SEMANTICS == (
        "task_submitted",
        "approval_required",
        "task_rejected",
        "task_working",
        "task_blocked",
        "artifact_available",
        "task_completed",
        "task_failed",
    )
