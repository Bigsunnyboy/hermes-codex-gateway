# Channel Contract

Hermes Agent Gateway treats Feishu/Lark as the current channel adapter, not as
Gateway Core or the only intended platform. A channel adapter converts platform
events into neutral gateway commands and converts gateway notifications back
into platform-specific messages.

## Inbound Command Shape

Gateway-facing code uses neutral channel shapes:

```python
ChannelActor(channel, actor_id, display_name)
DeliveryTarget(channel, conversation_id, reply_to_message_id)
ApprovalCardRef(channel, conversation_id, message_id, reply_to_message_id, kind)
ChannelCommand(channel, text, actor, delivery, message_id)
```

Channel adapters produce command payloads with:

```python
{
    "runner": str,
    "repo": str | None,
    "path": str | None,
    "mode": "read" | "write",
    "workspace_id": str | None,
    "agent_session_id": str | None,
    "verify_commands": list[str],
    "allowed_paths": list[str],
    "prompt": str,
}
```

Public chat commands must use `/agent`. The first supported runner example is:

```text
/agent runner=codex repo=example mode=read workspace=inspect-001
Summarize the repository. Do not modify files.
```

## Approval Callbacks

Interactive callbacks use `hermes_agent_action` with `approve` or `reject` and a
gateway queue task id.

For compatibility with existing queue records, serialized delivery data keeps
these field names:

```python
{
    "platform": "feishu" | "lark",
    "chat_id": str,
    "reply_to": str,  # optional
    "approval_card": {
        "platform": "feishu" | "lark",
        "chat_id": str,
        "message_id": str,
        "reply_to": str,  # optional
        "kind": "agent_write_approval",
    },
}
```

Neutral Gateway Core code should use boundary helpers to read and write those
compatibility fields. Raw event extraction, live adapter lookup, text sends,
interactive card sends, and card edits belong inside the Feishu/Lark facade.

Plugin runtime paths must inject channel sender and card-updater callables into
scheduler and delivery functions. Delivery code must not reach into live Hermes
runtime internals directly.

## Notifications

Notification text and cards use agent-generic labels:
- agent task queued;
- agent task approved;
- agent task rejected;
- agent task running;
- agent task done;
- agent task failed.

## Non-Goals For The Current Channel Phase

- No Slack, Telegram, REST, Web, or A2A adapter.
- No full channel abstraction rewrite beyond keeping public names neutral.
- No compatibility alias for old public commands.
