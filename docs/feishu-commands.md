# Feishu/Lark Channel Commands

The current channel adapter listens for `/agent` commands through the Hermes
Feishu/Lark gateway path. This is the first platform entry point, not the
gateway's long-term platform boundary.

## Read-Only Task

```text
/agent runner=codex repo=example mode=read workspace=smoke-read-001
  Analyze the project structure. Do not modify files.
```

Read tasks run immediately and should return a final result when the background
worker completes.

## Write Task

```text
/agent runner=codex repo=example mode=write workspace=fix-001 verify=pytest allow=app/
  Fix the failing test. Only modify files under app/.
```

Write tasks require approval. In Feishu, approve or reject the interactive card.
The same card is updated as the task moves through queued, running, done, or
failed states when Hermes exposes card update support.

## Manual Approval Fallback

If interactive cards are unavailable, send:

```text
/agent approve queued_YYYYMMDDTHHMMSSZ_xxxxxxxx
```

## Common Options

- `repo=<alias>`: repository alias from `config.json`.
- `path=<absolute-path>`: absolute path under an allowed workspace root.
- `mode=read|write`: gateway execution mode mapped to the selected runner.
- `workspace=<id>`: stable isolated git worktree handle.
- `session=<id>`: optional runner session id to resume.
- `verify=<template-or-shell>`: verification command or template.
- `allow=<path>[,<path>]`: write-mode changed-path allowlist.
