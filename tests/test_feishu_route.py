import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from hermes_local_agent_gateway.config import GatewayConfig
from hermes_local_agent_gateway.feishu_router import (
    build_card_action_callback_response,
    handle_pre_gateway_dispatch,
)
from hermes_local_agent_gateway.queue import FileTaskQueue


class FakeAdapter:
    def __init__(self) -> None:
        self.sent = []
        self.cards = []
        self.card_edits = []

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append(
            {
                "chat_id": chat_id,
                "content": content,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )

    async def _feishu_send_with_retry(self, *, chat_id, msg_type, payload, reply_to, metadata):
        self.cards.append(
            {
                "chat_id": chat_id,
                "msg_type": msg_type,
                "payload": payload,
                "reply_to": reply_to,
                "metadata": metadata,
            }
        )
        return SimpleNamespace(success=lambda: True, data=SimpleNamespace(message_id="msg-card"))

    async def edit_interactive_card(self, chat_id, message_id, card, finalize=False):
        self.card_edits.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "card": card,
                "finalize": finalize,
            }
        )
        return SimpleNamespace(success=True, message_id=message_id)


class PlatformKey:
    value = "feishu"


def _config_with_approval_policy(*, users=None, chats=None) -> GatewayConfig:
    root = Path("/tmp/hermes-codex-gateway-test")
    return GatewayConfig(
        workspace_roots=[root],
        repo_aliases={},
        artifact_root=root / "agent_tasks",
        worktree_root=root / "worktrees",
        session_root=root / "agent_sessions",
        approval_allowed_user_ids=list(users or []),
        approval_allowed_chat_ids=list(chats or []),
    )


def test_pre_gateway_dispatch_ignores_non_codex_messages(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    event = SimpleNamespace(text="hello", source=SimpleNamespace(platform="feishu", chat_id="chat-1"))

    result = handle_pre_gateway_dispatch(event=event, queue=queue)

    assert result == {"action": "allow"}


def test_pre_gateway_dispatch_enqueues_codex_command_and_sends_ack(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text="/codex repo=example-repo mode=read\nAnalyze only.",
        message_id="msg-1",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["action"] == "skip"
    assert result["reason"] == "codex-command-enqueued"
    assert result["task_id"].startswith("queued_")
    payload = queue.get(result["task_id"])["payload"]
    assert payload["prompt"] == "Analyze only."
    assert payload["delivery"] == {
        "platform": "feishu",
        "chat_id": "chat-1",
        "reply_to": "msg-1",
    }
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert adapter.sent[0]["chat_id"] == "chat-1"
    assert result["task_id"] in adapter.sent[0]["content"]


def test_pre_gateway_dispatch_sends_ack_with_platform_enum_adapter_key(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={PlatformKey(): adapter})
    event = SimpleNamespace(
        text="/codex repo=example-repo mode=read\nAnalyze only.",
        message_id="msg-1",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["action"] == "skip"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert adapter.sent[0]["chat_id"] == "chat-1"
    assert result["task_id"] in adapter.sent[0]["content"]


def test_pre_gateway_dispatch_approves_codex_task_by_slash_command(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"repo": "example-repo", "mode": "write", "prompt": "Fix it."})
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text=f"/codex approve {queued['task_id']}",
        message_id="msg-approve",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result == {
        "action": "skip",
        "reason": "codex-task-approved",
        "task_id": queued["task_id"],
        "status": "QUEUED",
    }
    assert queue.get(queued["task_id"])["approved"] is True
    assert queue.get(queued["task_id"])["status"] == "QUEUED"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert "Codex task approved" in adapter.sent[0]["content"]
    assert queued["task_id"] in adapter.sent[0]["content"]


def test_pre_gateway_dispatch_approves_codex_task_by_task_option(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"repo": "example-repo", "mode": "write", "prompt": "Fix it."})
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={PlatformKey(): adapter})
    event = SimpleNamespace(
        text=f"/codex approve task={queued['task_id']}",
        message_id="msg-approve",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["reason"] == "codex-task-approved"
    assert result["status"] == "QUEUED"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert adapter.sent[0]["chat_id"] == "chat-1"


def test_pre_gateway_dispatch_sends_approval_card_for_write_task(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text="/codex repo=example-repo mode=write workspace=fix verify=pytest allow=app/\nFix it.",
        message_id="msg-1",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["status"] == "APPROVAL_REQUIRED"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert adapter.cards[0]["msg_type"] == "interactive"
    saved = queue.get(result["task_id"])["payload"]["delivery"]["approval_card"]
    assert saved["message_id"] == "msg-card"
    assert saved["chat_id"] == "chat-1"
    card = json.loads(adapter.cards[0]["payload"])
    actions = card["elements"][-1]["actions"]
    values = [action["value"] for action in actions]
    assert values[0]["hermes_codex_action"] == "approve"
    assert values[1]["hermes_codex_action"] == "reject"
    assert values[0]["task_id"] == result["task_id"]
    assert not adapter.sent


def test_pre_gateway_dispatch_approves_codex_task_by_card_action(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"repo": "example-repo", "mode": "write", "prompt": "Fix it."})
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text=f'/card button {{"hermes_codex_action":"approve","task_id":"{queued["task_id"]}"}}',
        message_id="card-token",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1", user_id="ou_user"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["reason"] == "codex-task-approved"
    assert queue.get(queued["task_id"])["status"] == "QUEUED"


def test_pre_gateway_dispatch_denies_unauthorized_approval_user(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"repo": "example-repo", "mode": "write", "prompt": "Fix it."})
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text=f"/codex approve {queued['task_id']}",
        message_id="msg-approve",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1", user_id="ou_intruder"),
    )

    result = handle_pre_gateway_dispatch(
        event=event,
        gateway=gateway,
        queue=queue,
        cfg=_config_with_approval_policy(users=["ou_allowed"]),
    )

    assert result["reason"] == "codex-approve-unauthorized"
    assert result["status"] == "UNAUTHORIZED"
    assert queue.get(queued["task_id"])["status"] == "APPROVAL_REQUIRED"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert "operator is not in approval_allowed_user_ids" in adapter.sent[0]["content"]


def test_pre_gateway_dispatch_denies_approval_from_unapproved_chat(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"repo": "example-repo", "mode": "write", "prompt": "Fix it."})
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text=f"/codex approve {queued['task_id']}",
        message_id="msg-approve",
        source=SimpleNamespace(platform="feishu", chat_id="chat-denied", user_id="ou_allowed"),
    )

    result = handle_pre_gateway_dispatch(
        event=event,
        gateway=gateway,
        queue=queue,
        cfg=_config_with_approval_policy(users=["ou_allowed"], chats=["chat-allowed"]),
    )

    assert result["reason"] == "codex-approve-unauthorized"
    assert queue.get(queued["task_id"])["status"] == "APPROVAL_REQUIRED"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert "chat is not in approval_allowed_chat_ids" in adapter.sent[0]["content"]


def test_pre_gateway_dispatch_updates_approval_card_with_resolved_user_name(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "write",
            "prompt": "Fix it.",
            "delivery": {
                "platform": "feishu",
                "chat_id": "chat-1",
                "approval_card": {
                    "platform": "feishu",
                    "chat_id": "chat-1",
                    "message_id": "msg-card",
                },
            },
        }
    )
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text=f'/card button {{"hermes_codex_action":"approve","task_id":"{queued["task_id"]}"}}',
        message_id="card-token",
        source=SimpleNamespace(
            platform="feishu",
            chat_id="chat-1",
            user_id="ou_user",
            user_name="菜鸟",
        ),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["reason"] == "codex-task-approved"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert adapter.card_edits[0]["message_id"] == "msg-card"
    content = adapter.card_edits[0]["card"]["elements"][0]["content"]
    assert "菜鸟" in content
    assert "ou_user" not in content


def test_pre_gateway_dispatch_rejects_codex_task_by_card_action(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"repo": "example-repo", "mode": "write", "prompt": "Fix it."})
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text=f'/card button {{"hermes_codex_action":"reject","task_id":"{queued["task_id"]}"}}',
        message_id="card-token",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1", user_id="ou_user"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["reason"] == "codex-task-rejected"
    record = queue.get(queued["task_id"])
    assert record["status"] == "REJECTED"
    assert record["approval"]["rejected_by"] == "ou_user"


def test_card_action_callback_response_builds_approved_inline_card() -> None:
    result = build_card_action_callback_response(
        action_value={"hermes_codex_action": "approve", "task_id": "queued_1"},
        operator_name="Alice",
    )

    assert result is not None
    card = result["card"]
    assert card["header"]["template"] == "green"
    assert card["header"]["title"]["content"] == "Codex task approved"
    assert "queued_1" in card["elements"][0]["content"]
    assert "Alice" in card["elements"][0]["content"]


def test_card_action_callback_response_omits_raw_open_id_operator() -> None:
    result = build_card_action_callback_response(
        action_value={"hermes_codex_action": "approve", "task_id": "queued_1"},
        operator_name="ou_d3fc36251810ed3c449f5187f488c801",
    )

    assert result is not None
    assert "Operator:" not in result["card"]["elements"][0]["content"]


def test_card_action_callback_response_builds_unauthorized_inline_card() -> None:
    result = build_card_action_callback_response(
        action_value={"hermes_codex_action": "approve", "task_id": "queued_1"},
        operator_name="Alice",
        authorization_error="operator is not in approval_allowed_user_ids",
    )

    assert result is not None
    card = result["card"]
    assert card["header"]["title"]["content"] == "Codex approval denied"
    assert "UNAUTHORIZED" in card["elements"][0]["content"]
    assert "Alice" in card["elements"][0]["content"]


def test_card_action_callback_response_builds_rejected_inline_card() -> None:
    result = build_card_action_callback_response(
        action_value={"hermes_codex_action": "reject", "task_id": "queued_2"},
    )

    assert result is not None
    card = result["card"]
    assert card["header"]["template"] == "red"
    assert card["header"]["title"]["content"] == "Codex task rejected"
    assert "REJECTED" in card["elements"][0]["content"]


def test_card_action_callback_response_ignores_unrelated_actions() -> None:
    assert build_card_action_callback_response(action_value={"custom": "value"}) is None


def test_pre_gateway_dispatch_reports_codex_task_status(tmp_path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"repo": "example-repo", "mode": "write", "prompt": "Fix it."})
    adapter = FakeAdapter()
    gateway = SimpleNamespace(adapters={"feishu": adapter})
    event = SimpleNamespace(
        text=f"/codex status {queued['task_id']}",
        message_id="msg-status",
        source=SimpleNamespace(platform="feishu", chat_id="chat-1"),
    )

    result = handle_pre_gateway_dispatch(event=event, gateway=gateway, queue=queue)

    assert result["reason"] == "codex-task-status"
    assert result["status"] == "APPROVAL_REQUIRED"
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.sleep(0))
    assert "Codex task status" in adapter.sent[0]["content"]
    assert "APPROVAL_REQUIRED" in adapter.sent[0]["content"]
