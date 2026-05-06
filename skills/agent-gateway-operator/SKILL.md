# Agent Gateway Operator

Use this skill when operating Hermes Agent Gateway from Hermes Agent or a
messaging platform. The examples use the current Feishu/Lark channel adapter and
the current only enabled executable runner, `codex`.

## When To Use

- The user sends or asks about `/agent` commands.
- The user wants to approve, inspect, or troubleshoot queued agent tasks.
- The user wants to understand worktree isolation, verification, or allowlists.

## Rules

- Prefer `/agent runner=codex repo=<alias>` over raw absolute paths when an alias exists.
- Use `mode=read` for analysis and `mode=write` only for file changes.
- For write tasks, include both `verify=` and `allow=` whenever possible.
- Do not target `.env`, `*.key`, `*secret*`, `auth.json`, or `credentials*`.
- If a task reports `APPROVAL_REQUIRED`, use the channel approval card when
  available. Use `/agent approve <task_id>` only as fallback.

## Examples

Read-only:

```text
/agent runner=codex repo=example mode=read workspace=smoke-read-001
  Summarize the top-level project structure. Do not modify files.
```

Write:

```text
/agent runner=codex repo=example mode=write workspace=fix-tests-001 verify=pytest allow=app/,tests/
  Fix the failing tests. Only modify app/ and tests/.
```
