# Channel Contract

Hermes Agent Gateway treats Feishu/Lark as one channel adapter, not as Gateway
Core. A channel adapter converts platform events into neutral gateway commands
and converts gateway notifications back into platform-specific messages.

## Inbound Command Shape

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

Channel adapters may keep platform-specific delivery metadata, such as chat id
or message id, inside the delivery target object. Gateway Core should not depend
on Feishu raw event shapes.

## Notifications

Notification text and cards use agent-generic labels:
- agent task queued;
- agent task approved;
- agent task rejected;
- agent task running;
- agent task done;
- agent task failed.

## Non-Goals For Phase 1

- No Slack, Telegram, REST, Web, or A2A adapter.
- No full channel abstraction rewrite beyond keeping public names neutral.
- No compatibility alias for old public commands.
