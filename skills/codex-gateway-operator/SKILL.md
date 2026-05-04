# Codex Gateway Operator

Use this skill when operating Hermes Codex Gateway from Hermes Agent or a
messaging platform.

## When To Use

- The user sends or asks about `/codex` commands.
- The user wants to approve, inspect, or troubleshoot queued Codex tasks.
- The user wants to understand worktree isolation, verification, or allowlists.

## Rules

- Prefer `/codex repo=<alias>` over raw absolute paths when an alias exists.
- Use `mode=read` for analysis and `mode=write` only for file changes.
- For write tasks, include both `verify=` and `allow=` whenever possible.
- Do not target `.env`, `*.key`, `*secret*`, `auth.json`, or `credentials*`.
- If a task reports `APPROVAL_REQUIRED`, use the Feishu approval card when
  available. Use `/codex approve <task_id>` only as fallback.

## Examples

Read-only:

```text
/codex repo=example mode=read workspace=smoke-read-001
  Summarize the top-level project structure. Do not modify files.
```

Write:

```text
/codex repo=example mode=write workspace=fix-tests-001 verify=pytest allow=app/,tests/
  Fix the failing tests. Only modify app/ and tests/.
```
