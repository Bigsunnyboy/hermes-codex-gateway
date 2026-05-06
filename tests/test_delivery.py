import json
from pathlib import Path

from hermes_agent_gateway.delivery import (
    build_task_lifecycle_card,
    deliver_task_result,
    update_task_lifecycle_card,
)
from hermes_agent_gateway.queue import FileTaskQueue


def test_deliver_task_result_sends_final_output_and_marks_record(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    artifact_dir = tmp_path / "artifacts" / "task-1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "agent_stdout.jsonl").write_text(
        json.dumps({"type": "agent_message", "message": "Final analysis result."}) + "\n",
        encoding="utf-8",
    )
    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze.",
            "delivery": {
                "platform": "feishu",
                "chat_id": "oc_123",
                "reply_to": "om_msg",
            },
        }
    )
    queue.complete(
        queued["task_id"],
        {
            "success": True,
            "status": "DONE",
            "task_id": "agent_task_1",
            "artifact_dir": str(artifact_dir),
            "project_path": "/home/projects/example-repo",
            "execution_path": "/home/projects/example-repo",
            "workspace_id": None,
            "returncode": 0,
            "workspace_changed": False,
            "verify_results": [],
        },
    )
    sends = []

    def fake_sender(**kwargs):
        sends.append(kwargs)
        return {"success": True, "message_id": "sent-1"}

    result = deliver_task_result(queue, task_id=queued["task_id"], adapter_sender=fake_sender)

    assert result["status"] == "DELIVERED"
    assert result["target"] == "feishu:oc_123"
    assert sends[0]["platform"] == "feishu"
    assert sends[0]["chat_id"] == "oc_123"
    assert sends[0]["reply_to"] == "om_msg"
    assert sends[0]["message"] == "Final analysis result."
    assert queue.get(queued["task_id"])["delivery_result"]["status"] == "DELIVERED"


def test_update_task_lifecycle_card_updates_saved_feishu_card(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "mode": "write",
            "prompt": "Run.",
            "delivery": {
                "platform": "feishu",
                "chat_id": "oc_123",
                "approval_card": {
                    "platform": "feishu",
                    "chat_id": "oc_123",
                    "message_id": "om_card",
                },
            },
        }
    )
    queue.complete(
        queued["task_id"],
        {"success": True, "status": "DONE", "returncode": 0, "workspace_id": "w1"},
    )
    updates = []

    def fake_update(**kwargs):
        updates.append(kwargs)
        return {"success": True, "message_id": kwargs["message_id"]}

    record = queue.get(queued["task_id"])
    result = update_task_lifecycle_card(queue, record, phase="DONE", card_updater=fake_update)

    assert result["success"] is True
    assert updates[0]["message_id"] == "om_card"
    assert updates[0]["card"]["header"]["title"]["content"] == "Agent task done"
    assert queue.get(queued["task_id"])["card_updates"][0]["phase"] == "DONE"


def test_deliver_task_result_prefers_card_update_when_approval_card_exists(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "mode": "write",
            "prompt": "Run.",
            "delivery": {
                "platform": "feishu",
                "chat_id": "oc_123",
                "reply_to": "om_original",
                "approval_card": {
                    "platform": "feishu",
                    "chat_id": "oc_123",
                    "message_id": "om_card",
                },
            },
        }
    )
    queue.complete(queued["task_id"], {"success": True, "status": "DONE", "returncode": 0})
    sends = []
    updates = []

    result = deliver_task_result(
        queue,
        task_id=queued["task_id"],
        adapter_sender=lambda **kwargs: sends.append(kwargs) or {"success": True},
        card_updater=lambda **kwargs: updates.append(kwargs) or {"success": True, "message_id": "om_card"},
    )

    assert result["status"] == "DELIVERED"
    assert result["method"] == "card_update"
    assert not sends
    assert updates[0]["message_id"] == "om_card"
    assert queue.get(queued["task_id"])["delivery_result"]["method"] == "card_update"


def test_deliver_task_result_falls_back_to_text_when_card_update_fails(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "mode": "write",
            "prompt": "Run.",
            "delivery": {
                "platform": "feishu",
                "chat_id": "oc_123",
                "approval_card": {
                    "platform": "feishu",
                    "chat_id": "oc_123",
                    "message_id": "om_card",
                },
            },
        }
    )
    queue.complete(queued["task_id"], {"success": False, "status": "FAILED", "error": "boom"})
    sends = []

    result = deliver_task_result(
        queue,
        task_id=queued["task_id"],
        adapter_sender=lambda **kwargs: sends.append(kwargs) or {"success": True, "message_id": "om_text"},
        card_updater=lambda **kwargs: {"success": False, "error": "cannot update"},
    )

    assert result["status"] == "DELIVERED"
    assert "method" not in result
    assert sends
    assert "Agent task finished" in sends[0]["message"]


def test_build_task_lifecycle_card_renders_failed_state() -> None:
    card = build_task_lifecycle_card(
        {
            "task_id": "queued_1",
            "status": "FAILED",
            "payload": {"mode": "write", "path": "/repo", "workspace_id": "w1"},
            "result": {"success": False, "error": "bad", "returncode": 1},
        },
        phase="FAILED",
    )

    assert card["header"]["template"] == "red"
    assert "Agent task failed" == card["header"]["title"]["content"]
    assert "bad" in card["elements"][0]["content"]


def test_deliver_task_result_extracts_nested_agent_message(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    artifact_dir = tmp_path / "artifacts" / "task-1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "agent_stdout.jsonl").write_text(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "1. 当前路径：`/workspace`\n2. 是否为 git 仓库：是\n3. 顶层目录列表摘要：`app`、`tests`",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze.",
            "delivery": {"platform": "feishu", "chat_id": "oc_123"},
        }
    )
    queue.complete(
        queued["task_id"],
        {
            "success": True,
            "status": "DONE",
            "artifact_dir": str(artifact_dir),
            "returncode": 0,
        },
    )
    sends = []

    def fake_sender(**kwargs):
        sends.append(kwargs)
        return {"success": True, "message_id": "sent-1"}

    result = deliver_task_result(queue, task_id=queued["task_id"], adapter_sender=fake_sender)

    assert result["status"] == "DELIVERED"
    assert sends[0]["message"].startswith("1. 当前路径")
    assert "Agent task finished" not in sends[0]["message"]
    assert "Artifacts:" not in sends[0]["message"]


def test_deliver_task_result_preserves_multiple_assistant_messages(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    artifact_dir = tmp_path / "artifacts" / "task-1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "agent_stdout.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"type": "agent_message", "message": "First useful result."}),
                json.dumps({"type": "agent_message", "message": "Second useful result."}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze.",
            "delivery": {"platform": "feishu", "chat_id": "oc_123"},
        }
    )
    queue.complete(
        queued["task_id"],
        {
            "success": True,
            "status": "DONE",
            "artifact_dir": str(artifact_dir),
            "returncode": 0,
        },
    )
    sends = []

    result = deliver_task_result(
        queue,
        task_id=queued["task_id"],
        adapter_sender=lambda **kwargs: sends.append(kwargs) or {"success": True},
    )

    assert result["status"] == "DELIVERED"
    assert sends[0]["message"] == "First useful result.\n\nSecond useful result."


def test_deliver_task_result_is_idempotent_after_success(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "mode": "read",
            "prompt": "Analyze.",
            "delivery": {"platform": "feishu", "chat_id": "oc_123"},
        }
    )
    queue.complete(queued["task_id"], {"success": True, "status": "DONE"})
    calls = []

    def fake_sender(**kwargs):
        calls.append(kwargs)
        return {"success": True}

    first = deliver_task_result(queue, task_id=queued["task_id"], adapter_sender=fake_sender)
    second = deliver_task_result(queue, task_id=queued["task_id"], adapter_sender=fake_sender)

    assert first["status"] == "DELIVERED"
    assert second["status"] == "ALREADY_DELIVERED"
    assert len(calls) == 1


def test_deliver_task_result_falls_back_to_send_message_tool(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "mode": "read",
            "prompt": "Analyze.",
            "delivery": {"platform": "feishu", "chat_id": "oc_123"},
        }
    )
    queue.complete(queued["task_id"], {"success": True, "status": "DONE"})
    tool_calls = []

    def failing_adapter(**kwargs):
        return {"success": False, "error": "adapter unavailable"}

    def fake_tool(args):
        tool_calls.append(args)
        return json.dumps({"success": True, "message_id": "tool-sent"})

    result = deliver_task_result(
        queue,
        task_id=queued["task_id"],
        adapter_sender=failing_adapter,
        tool_sender=fake_tool,
    )

    assert result["status"] == "DELIVERED"
    assert tool_calls[0]["target"] == "feishu:oc_123"
    assert "Agent task finished" in tool_calls[0]["message"]
