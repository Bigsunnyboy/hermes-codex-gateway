import json
import os
import pytest

from pathlib import Path

from hermes_agent_gateway.a2a_gateway_contract import (
    EVENT_SEMANTICS,
    artifact_manifest,
    artifact_views,
    build_gateway_agent_descriptor,
    gateway_task_record_view,
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


def test_queue_record_view_preserves_queue_identity_and_status_precedence(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "task.json").write_text(
        json.dumps(
            {
                "task_id": "agent_1",
                "status": "DONE",
                "project_path": "/home/projects/repo",
                "prompt": "Inspect",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    record = {
        "task_id": "queued_1",
        "status": "FAILED",
        "created_at": "2026-05-06T00:00:00Z",
        "updated_at": "2026-05-06T00:01:00Z",
        "payload": {"runner": "codex", "mode": "read", "prompt": "Inspect"},
        "result": {
            "success": False,
            "status": "DONE",
            "task_id": "agent_1",
            "artifact_dir": str(artifact_dir),
            "error": "failed at /home/projects/repo/app.py",
        },
    }

    view = gateway_task_record_view(record)

    assert view["task_id"] == "queued_1"
    assert view["execution_task_id"] == "agent_1"
    assert view["state"]["state"] == "failed"
    assert view["status"] == "FAILED"
    assert "result.status differs from queue status" in view["mismatches"]
    assert "task_record.status differs from queue status" in view["mismatches"]
    assert view["payload"]["prompt"]["content"] == "Inspect"
    assert view["result"]["error"]["content"] == "failed at <redacted-path>"
    assert view["artifacts"]["items"]["task_record"]["payload"]["task_id"] == "agent_1"
    assert view["artifacts"]["items"]["task_record"]["payload"]["project_path"] == "<redacted-path>"


def test_queue_done_remains_completed_when_artifact_status_disagrees(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "task.json").write_text(
        json.dumps({"task_id": "agent_1", "status": "FAILED"}) + "\n",
        encoding="utf-8",
    )

    view = gateway_task_record_view(
        {
            "task_id": "queued_1",
            "status": "DONE",
            "payload": {"mode": "read"},
            "result": {"success": False, "task_id": "agent_1", "artifact_dir": str(artifact_dir)},
        }
    )

    assert view["state"]["state"] == "completed"
    assert view["execution_task_id"] == "agent_1"
    assert "task_record.status differs from queue status" in view["mismatches"]


def test_artifact_manifest_reads_allowlisted_files_with_preview_metadata(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    artifact_dir.mkdir(parents=True)
    large_stdout = "x" * (16 * 1024 + 20)
    large_diff = "d" * (64 * 1024 + 20)
    (artifact_dir / "agent_stdout.jsonl").write_text(large_stdout, encoding="utf-8")
    (artifact_dir / "agent_stderr.log").write_text("error at /tmp/repo/file.py", encoding="utf-8")
    (artifact_dir / "after_diff.txt").write_text(large_diff, encoding="utf-8")
    (artifact_dir / "ignored.txt").write_text("not included", encoding="utf-8")

    manifest = artifact_manifest(artifact_dir)

    assert set(manifest["items"]) == {"stdout", "stderr", "after_diff"}
    assert manifest["items"]["stdout"]["truncated"] is True
    assert manifest["items"]["stdout"]["bytes_read"] == 16 * 1024
    assert manifest["items"]["stdout"]["limit_bytes"] == 16 * 1024
    assert manifest["items"]["stderr"]["content"] == "error at <redacted-path>"
    assert manifest["items"]["after_diff"]["truncated"] is True
    assert manifest["items"]["after_diff"]["bytes_read"] == 64 * 1024
    assert "ignored" not in manifest["items"]


def test_artifact_manifest_omits_symlink_escape(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    outside = tmp_path / "outside.log"
    artifact_dir.mkdir(parents=True)
    outside.write_text("secret", encoding="utf-8")
    os.symlink(outside, artifact_dir / "agent_stdout.jsonl")

    manifest = artifact_manifest(artifact_dir)

    assert "stdout" not in manifest["items"]


def test_artifact_manifest_handles_invalid_json_without_crashing(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "task.json").write_text("{not json /home/projects/repo", encoding="utf-8")
    (artifact_dir / "verify_results.json").write_text("{not json /tmp/verify", encoding="utf-8")

    manifest = artifact_manifest(artifact_dir)

    assert manifest["items"]["task_record_error"]["payload"]["error"] == "invalid json"
    assert manifest["items"]["task_record_error"]["payload"]["path"] == "<redacted-path>"
    assert manifest["items"]["verification_error"]["payload"]["error"] == "invalid json"


def test_verify_logs_are_read_only_from_fixed_contained_basenames(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    artifact_dir.mkdir(parents=True)
    external_stdout = tmp_path / "external" / "verify_1_stdout.log"
    external_stdout.parent.mkdir()
    external_stdout.write_text("external secret", encoding="utf-8")
    (artifact_dir / "verify_1_stdout.log").write_text("local stdout /home/projects/repo", encoding="utf-8")
    (artifact_dir / "verify_1_stderr.log").write_text("local stderr", encoding="utf-8")
    (artifact_dir / "verify_2_stdout.log").write_text("unreferenced", encoding="utf-8")
    (artifact_dir / "verify_results.json").write_text(
        json.dumps(
            [
                {
                    "command": "test -f generated.txt",
                    "returncode": 0,
                    "stdout": str(external_stdout),
                    "stderr": "/outside/verify_1_stderr.log",
                }
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = artifact_manifest(artifact_dir)
    verification = manifest["items"]["verification"]["payload"]

    assert verification["results"][0]["stdout"] == "<redacted-path>"
    assert verification["results"][0]["stderr"] == "<redacted-path>"
    assert verification["logs"][0]["stdout"]["content"] == "local stdout <redacted-path>"
    assert verification["logs"][0]["stderr"]["content"] == "local stderr"
    assert "verify_2_stdout" not in str(verification)


def test_prompt_and_error_previews_are_bounded() -> None:
    long_prompt = "p" * (8 * 1024 + 10)
    view = gateway_task_record_view(
        {
            "task_id": "queued_1",
            "status": "FAILED",
            "payload": {"prompt": long_prompt},
            "result": {"success": False, "error": "e" * (8 * 1024 + 10)},
        }
    )

    assert view["payload"]["prompt"]["truncated"] is True
    assert view["payload"]["prompt"]["bytes_read"] == 8 * 1024
    assert view["result"]["error"]["truncated"] is True
    assert view["result"]["error"]["limit_bytes"] == 8 * 1024
