# Runner Contract

Hermes Agent Gateway invokes external agent runners through a narrow contract.
Gateway Core owns governance; runner implementations own invocation details and
output normalization.

## Responsibilities

Gateway Core:
- resolve the target repository;
- prepare the execution workspace;
- enforce approval, risk policy, path guard, verification, artifact capture, and audit;
- persist task and session metadata using gateway-neutral field names.

Runner implementation:
- map `mode=read|write` to its safest available permission model;
- build the concrete subprocess or runtime request;
- write bounded stdout/stderr artifacts;
- normalize exit status and session id into the gateway result shape.

## First Runner

The first supported explicit runner id is `codex`.

Public task creation must still pass `runner=codex`; there is no implicit
default. The implementation details for that runner live under runner-private
modules and must not become public tool, command, callback, queue, or session
field names.

## Result Shape

Runner results passed back to Gateway Core use:

```python
{
    "command": list[str],
    "returncode": int | None,
    "duration_seconds": float | None,
    "agent_session_id": str | None,
}
```

Additional runner-specific metadata belongs under a nested metadata field in
future phases.

## Permission Mapping

Read mode:
- use the runner's safest read or planning mode when available;
- workspace changes after execution cause task failure.

Write mode:
- requires approval before execution;
- runs in an isolated worktree when possible;
- must not bypass gateway path and verification gates.

## Non-Goals For Phase 1

- No additional runners.
- No A2A HTTP endpoints.
- No streaming or subscribe behavior.
- No upstream Hermes runtime/core changes.
