# Safety Model

Hermes Codex Gateway adds a governance layer around local Codex execution.

## Isolation

- Each task runs in a managed git worktree under `worktree_root`.
- Existing user changes in the source repository are not modified by Codex.
- Stable `workspace=` values can resume context while remaining isolated from
  other worktrees.

## Risk Handling

- `mode=read` is low risk and does not require approval.
- `mode=write` requires approval.
- Sensitive prompts and targets are blocked instead of approved when they mention
  `.env`, `*.key`, `*secret*`, `auth.json`, `credentials*`, destructive shell
  patterns, or force-push/drop-database style operations.

## Post-Run Guardrails

- Verification templates are expanded before execution.
- Write tasks can declare `allow=` paths. Changes outside that allowlist fail the
  task even if Codex exits successfully.
- Output capture is size-limited by `max_output_bytes`.

## Limits

This plugin is not a sandbox escape boundary. Use OS permissions, repository
permissions, low-privilege credentials, and network controls appropriate for the
host where Hermes runs.
