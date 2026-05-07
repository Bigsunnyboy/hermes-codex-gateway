import json
import os
from pathlib import Path

import pytest

from hermes_agent_gateway import a2a_gateway_contract
from hermes_agent_gateway.adapter_projection_service import AdapterProjectionService


def test_service_descriptor_matches_current_gateway_projection() -> None:
    service = AdapterProjectionService()

    descriptor = service.gateway_descriptor()

    assert descriptor.enabled_runners == ("codex",)
    assert {runner.id for runner in descriptor.runner_capabilities} == {"codex"}
    assert {"claude-code", "qoder", "deepseek-tui"}.isdisjoint(descriptor.enabled_runners)
    assert descriptor.protocol_capabilities.streaming is False
    assert descriptor.protocol_capabilities.subscription_updates is False
    assert descriptor.protocol_capabilities.push_notifications is False
    assert descriptor.protocol_capabilities.public_endpoints is False
    assert descriptor.governance.approval_required_for_write is True
    assert descriptor.governance.path_guard is True


def test_service_accepts_neutral_actor_sources_without_a2a_lock_in() -> None:
    service = AdapterProjectionService()

    envelope = service.normalize_message_envelope(
        {
            "runner": "codex",
            "mode": "read",
            "prompt": "Inspect only.",
            "actor": {
                "source": "cli",
                "actor_id": "user-1",
                "display_name": "User One",
            },
        }
    )

    assert envelope.actor is not None
    assert envelope.actor.source == "cli"
    assert envelope.actor.actor_id == "user-1"
    assert service.message_payload(envelope) == {
        "runner": "codex",
        "mode": "read",
        "prompt": "Inspect only.",
        "verify_commands": [],
        "allowed_paths": [],
    }


def test_service_uses_neutral_actor_source_default() -> None:
    envelope = AdapterProjectionService().normalize_message_envelope(
        {
            "runner": "codex",
            "mode": "read",
            "prompt": "Inspect only.",
            "actor": {"actor_id": "user-1"},
        }
    )

    assert envelope.actor is not None
    assert envelope.actor.source == "adapter"


def test_a2a_facade_preserves_a2a_actor_source_validation() -> None:
    with pytest.raises(ValueError, match="actor.source must be a2a"):
        a2a_gateway_contract.normalize_message_envelope(
            {
                "runner": "codex",
                "mode": "read",
                "prompt": "Inspect only.",
                "actor": {"source": "cli", "actor_id": "user-1"},
            }
        )


def test_a2a_facade_defaults_missing_actor_source_to_a2a() -> None:
    envelope = a2a_gateway_contract.normalize_message_envelope(
        {
            "runner": "codex",
            "mode": "read",
            "prompt": "Inspect only.",
            "actor": {"actor_id": "user-1"},
        }
    )

    assert envelope.actor is not None
    assert envelope.actor.source == "a2a"


def test_service_normalizes_required_actor_source() -> None:
    envelope = AdapterProjectionService().normalize_adapter_message_envelope(
        {
            "runner": "codex",
            "mode": "read",
            "prompt": "Inspect only.",
            "actor": {"source": "A2A", "actor_id": "user-1"},
        },
        actor_source="A2A",
    )

    assert envelope.actor is not None
    assert envelope.actor.source == "a2a"


def test_service_task_record_view_is_adapter_entrypoint_for_artifacts(tmp_path: Path) -> None:
    service = AdapterProjectionService()
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
    (artifact_dir / "agent_stdout.jsonl").write_text("ok at /home/projects/repo\n", encoding="utf-8")

    view = service.task_record_view(
        {
            "task_id": "queued_1",
            "status": "FAILED",
            "payload": {"runner": "codex", "mode": "read", "prompt": "Inspect"},
            "result": {
                "success": False,
                "status": "DONE",
                "task_id": "agent_1",
                "artifact_dir": str(artifact_dir),
                "error": "failed at /home/projects/repo/app.py",
            },
        }
    )

    assert view["task_id"] == "queued_1"
    assert view["execution_task_id"] == "agent_1"
    assert view["status"] == "FAILED"
    assert view["state"]["state"] == "failed"
    assert "result.status differs from queue status" in view["mismatches"]
    assert "task_record.status differs from queue status" in view["mismatches"]
    assert view["payload"]["prompt"]["content"] == "Inspect"
    assert view["result"]["error"]["content"] == "failed at <redacted-path>"
    assert view["artifacts"]["items"]["stdout"]["content"] == "ok at <redacted-path>\n"
    assert view["artifacts"]["items"]["task_record"]["payload"]["project_path"] == "<redacted-path>"


def test_service_artifact_manifest_remains_bounded_internal_plumbing(tmp_path: Path) -> None:
    service = AdapterProjectionService()
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    outside = tmp_path / "outside.log"
    artifact_dir.mkdir(parents=True)
    outside.write_text("secret", encoding="utf-8")
    os.symlink(outside, artifact_dir / "agent_stdout.jsonl")
    (artifact_dir / "agent_stderr.log").write_text("error at /tmp/repo/file.py", encoding="utf-8")
    (artifact_dir / "verify_results.json").write_text("{not json /tmp/verify", encoding="utf-8")

    manifest = service.artifact_manifest(artifact_dir)

    assert "stdout" not in manifest["items"]
    assert manifest["items"]["stderr"]["content"] == "error at <redacted-path>"
    assert manifest["items"]["verification_error"]["payload"]["error"] == "invalid json"
    assert manifest["items"]["stderr"]["limit_bytes"] == 16 * 1024


def test_service_artifact_views_and_sanitization_match_existing_projection() -> None:
    service = AdapterProjectionService()
    record = {
        "status": "DONE",
        "stdout": "ok from /home/projects/repo",
        "diff": "diff --git",
        "verify_results": [{"command": "pytest", "returncode": 0}],
        "risk": {"level": "low"},
        "project_path": "/home/projects/repo",
    }

    service_views = service.artifact_views(record)
    facade_views = a2a_gateway_contract.artifact_views(record)

    assert service_views == facade_views
    assert service.sanitize_task_record(record) == a2a_gateway_contract.sanitize_task_record(record)


def test_a2a_facade_delegates_representative_projections(tmp_path: Path) -> None:
    service = AdapterProjectionService()
    artifact_dir = tmp_path / "artifacts" / "agent_1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "task.json").write_text(json.dumps({"task_id": "agent_1"}) + "\n", encoding="utf-8")
    record = {
        "task_id": "queued_1",
        "status": "DONE",
        "payload": {"runner": "codex", "mode": "read", "prompt": "Inspect"},
        "result": {"success": True, "task_id": "agent_1", "artifact_dir": str(artifact_dir)},
    }
    envelope_payload = {
        "runner": "codex",
        "mode": "read",
        "prompt": "Inspect only.",
        "actor": {"source": "a2a", "actor_id": "user-1"},
    }

    assert a2a_gateway_contract.build_gateway_agent_descriptor() == service.gateway_descriptor()
    assert a2a_gateway_contract.normalize_message_envelope(
        envelope_payload
    ) == service.normalize_message_envelope(envelope_payload)
    assert a2a_gateway_contract.gateway_task_record_view(record) == service.task_record_view(record)
    assert a2a_gateway_contract.artifact_manifest(artifact_dir) == service.artifact_manifest(artifact_dir)
