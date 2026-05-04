# Feishu Commands

The plugin listens for `/codex` commands through the Hermes Feishu gateway.

## Read-Only Task

```text
/codex repo=example mode=read workspace=smoke-read-001
  Analyze the project structure. Do not modify files.
```

Read tasks run immediately and should return a final result when the background
worker completes.

## Write Task

```text
/codex repo=example mode=write workspace=fix-001 verify=pytest allow=app/
  Fix the failing test. Only modify files under app/.
```

Write tasks require approval. In Feishu, approve or reject the interactive card.
The same card is updated as the task moves through queued, running, done, or
failed states when Hermes exposes card update support.

## Manual Approval Fallback

If interactive cards are unavailable, send:

```text
/codex approve queued_YYYYMMDDTHHMMSSZ_xxxxxxxx
```

## Common Options

- `repo=<alias>`: repository alias from `config.json`.
- `path=<absolute-path>`: absolute path under an allowed workspace root.
- `mode=read|write`: Codex sandbox mode.
- `workspace=<id>`: stable isolated git worktree handle.
- `session=<id>`: optional Codex session id to resume.
- `verify=<template-or-shell>`: verification command or template.
- `allow=<path>[,<path>]`: write-mode changed-path allowlist.
