# Hermes Codex Gateway

Hermes Codex Gateway is an opt-in Hermes Agent plugin for governed local Codex
execution from messaging platforms, especially Feishu/Lark.

It turns a Feishu `/codex ...` command into an auditable background task:

```text
Feishu /codex -> Hermes plugin hook -> queue -> cron wake gate -> isolated git worktree -> codex exec -> verify -> Feishu result/card update
```

## What It Provides

- Feishu `/codex` command parsing before normal agent dispatch.
- Read and write execution modes.
- Git worktree isolation per `workspace=...`.
- Write-mode approval gate with Feishu interactive cards when the Hermes
  Feishu adapter exposes card callbacks.
- Optional `allow=...` changed-path enforcement.
- Optional `verify=...` command templates.
- Captured artifacts for each task.
- Result delivery back to the original Feishu chat.
- Cron wake gate that returns `{"wakeAgent": false}` while the queue is empty,
  so empty ticks do not start an LLM session.
- Managed `CODEX_HOME` for gateway-launched Codex subprocesses, avoiding user
  hooks that can mutate target worktrees.

## Requirements

- Hermes Agent with plugin support.
- Codex CLI available on the gateway host.
- A Hermes messaging gateway. Feishu/Lark is the primary tested platform.
- A git repository for worktree-isolated execution.

For full Feishu card lifecycle updates, Hermes needs the generic Feishu adapter
hooks for interactive card updates and card action callback responses. Without
those hooks, text fallback commands and result delivery still work, but the rich
card lifecycle is reduced.

## Install

From GitHub once this repository is published:

```bash
hermes plugins install <owner>/hermes-codex-gateway
hermes plugins enable hermes-codex-gateway
systemctl restart hermes-gateway.service
```

Copy and edit the example config if you need custom roots, aliases, proxy
variables, or quota settings:

```bash
cp ~/.hermes/plugins/hermes-codex-gateway/config.example.json \
  ~/.hermes/plugins/hermes-codex-gateway/config.json
```

Do not put API keys, Feishu secrets, Codex auth files, or project credentials in
the plugin config.

## Configure

Important config fields:

- `workspace_roots`: project roots the plugin may target.
- `repo_aliases`: short names used by `/codex repo=...`.
- `artifact_root`: completed task artifacts.
- `worktree_root`: isolated Codex worktrees.
- `worktree_archive_root`: optional archived worktree root.
- `session_root`: saved Codex session ids keyed by workspace.
- `codex_env`: optional non-secret environment overrides for Codex subprocesses.
- `max_output_bytes`: per-stream stdout/stderr capture limit.
- `approval_allowed_user_ids`: optional Feishu open_id allowlist.
- `approval_allowed_chat_ids`: optional Feishu chat allowlist.

Run once after enabling:

```text
ensure_codex_worker_cron
```

That creates or repairs the Hermes cron worker named `codex-queue-worker`.

## Feishu Commands

Read-only analysis:

```text
/codex repo=example mode=read workspace=example-read-001
Summarize the project structure. Do not modify files.
```

Approved write:

```text
/codex repo=example mode=write workspace=docs-update-001 verify=file:docs/example.md allow=docs/example.md
Update docs/example.md. Do not modify any other file.
```

Text approval fallback:

```text
/codex approve queued_...
/codex reject queued_...
/codex status queued_...
```

## Safety Model

- Read mode uses Codex read-only sandboxing.
- Write mode requires approval.
- Critical sensitive/destructive prompts are blocked.
- Sensitive targets such as `.env`, `*.key`, `*secret*`, `auth.json`, and
  `credentials*` are denied.
- Governance paths such as `.git`, `.codex`, `.omx`, `.hermes`, and this plugin
  are protected.
- Work happens in an isolated git worktree when the target repository has a
  valid `HEAD`.
- `allow=...` fails the task if Codex changes unexpected paths.
- `verify=...` runs after Codex and before final success is reported.

## Operator Skill

This repository ships an operator skill at
`skills/codex-gateway-operator/SKILL.md`. It is intended for teams using the
plugin from chat and covers command templates, approval guidance, smoke tests,
and troubleshooting.

## Development

Run plugin tests from the repository root:

```bash
PYTHONPATH=. python -m pytest tests -q
```

Run the repository hygiene check before publishing:

```bash
scripts/sanitize-check.sh
```

Run the official Docker install smoke test before tagging a release:

```bash
scripts/docker-official-smoke.sh https://github.com/<owner>/hermes-codex-gateway.git
```

For local pre-publish validation, pass the repository path:

```bash
scripts/docker-official-smoke.sh /path/to/hermes-codex-gateway
```

## Publishing Notes

This repository is designed as an external plugin, not as a bundled Hermes
plugin. The upstream Hermes PR surface should stay focused on generic Feishu
adapter extension points, while this repository owns Codex-specific queueing,
policy, worktree isolation, and operator documentation.

## License

MIT. See [LICENSE](LICENSE).
