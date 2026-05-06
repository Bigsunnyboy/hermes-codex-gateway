# Hermes Agent Gateway

[![Release](https://img.shields.io/github/v/release/Bigsunnyboy/hermes-agent-gateway?include_prereleases)](https://github.com/Bigsunnyboy/hermes-agent-gateway/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

Run governed local agent tasks from Feishu/Lark through Hermes Agent.

Hermes Agent Gateway is an opt-in Hermes Agent plugin for teams that want chat
operators to start local agent work without giving up approval gates, worktree
isolation, path allowlists, verification commands, and auditable artifacts.

It turns a Feishu `/agent ...` command into an auditable background task:

```text
Feishu /agent -> Hermes plugin hook -> queue -> cron wake gate -> isolated git worktree -> selected runner -> verify -> Feishu result/card update
```

## Quick Start

```bash
hermes plugins install Bigsunnyboy/hermes-agent-gateway
hermes plugins enable hermes-agent-gateway
systemctl restart hermes-gateway.service
```

Create a config from the example:

```bash
cp ~/.hermes/plugins/hermes-agent-gateway/config.example.json \
  ~/.hermes/plugins/hermes-agent-gateway/config.json
```

Then try a read-only task from Feishu/Lark:

```text
/agent runner=codex repo=example mode=read workspace=first-read
Summarize the project structure. Do not modify files.
```

For a 90-second walkthrough script, see [docs/demo.md](docs/demo.md).

## Why This Exists

Running an agent from chat is useful, but write-capable local automation needs
guardrails. This plugin keeps runner-specific behavior outside Hermes core while
providing a practical operator workflow:

- Feishu/Lark remains the chat control plane.
- Hermes Agent owns plugin loading, gateway dispatch, and cron wakeups.
- The selected runner executes inside isolated worktrees.
- Write tasks require approval and can be constrained by `allow=...`.
- `verify=...` commands run before success is reported.
- Artifacts are captured for audit and follow-up.

## What It Provides

- Feishu `/agent` command parsing before normal agent dispatch.
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
- Managed `CODEX_HOME` for gateway-launched runner subprocesses, avoiding user
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

```bash
hermes plugins install Bigsunnyboy/hermes-agent-gateway
hermes plugins enable hermes-agent-gateway
systemctl restart hermes-gateway.service
```

Copy and edit the example config if you need custom roots, aliases, proxy
variables, or quota settings:

```bash
cp ~/.hermes/plugins/hermes-agent-gateway/config.example.json \
  ~/.hermes/plugins/hermes-agent-gateway/config.json
```

Do not put API keys, Feishu secrets, runner auth files, or project credentials in
the plugin config.

## Configure

Important config fields:

- `workspace_roots`: project roots the plugin may target.
- `repo_aliases`: short names used by `/agent runner=codex repo=...`.
- `artifact_root`: completed task artifacts.
- `worktree_root`: isolated agent worktrees.
- `worktree_archive_root`: optional archived worktree root.
- `session_root`: saved runner session ids keyed by workspace.
- `codex_env`: optional non-secret environment overrides for runner subprocesses.
- `max_output_bytes`: per-stream stdout/stderr capture limit.
- `approval_allowed_user_ids`: optional Feishu open_id allowlist.
- `approval_allowed_chat_ids`: optional Feishu chat allowlist.

Run once after enabling:

```text
ensure_agent_worker_cron
```

That creates or repairs the Hermes cron worker named `agent-queue-worker`.

## Feishu Commands

Read-only analysis:

```text
/agent runner=codex repo=example mode=read workspace=example-read-001
Summarize the project structure. Do not modify files.
```

Approved write:

```text
/agent runner=codex repo=example mode=write workspace=docs-update-001 verify=file:docs/example.md allow=docs/example.md
Update docs/example.md. Do not modify any other file.
```

Text approval fallback:

```text
/agent approve queued_...
/agent reject queued_...
/agent status queued_...
```

## Safety Model

- Read mode maps to the selected runner's safest available read behavior.
- Write mode requires approval.
- Critical sensitive/destructive prompts are blocked.
- Sensitive targets such as `.env`, `*.key`, `*secret*`, `auth.json`, and
  `credentials*` are denied.
- Governance paths such as `.git`, `.codex`, `.omx`, `.hermes`, and this plugin
  are protected.
- Work happens in an isolated git worktree when the target repository has a
  valid `HEAD`.
- `allow=...` fails the task if the selected runner changes unexpected paths.
- `verify=...` runs after the selected runner and before final success is reported.

## Operator Skill

This repository ships an operator skill at
`skills/agent-gateway-operator/SKILL.md`. It is intended for teams using the
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
scripts/docker-official-smoke.sh https://github.com/Bigsunnyboy/hermes-agent-gateway.git
```

For local pre-publish validation, pass the repository path:

```bash
scripts/docker-official-smoke.sh /path/to/hermes-agent-gateway
```

## Publishing Notes

This repository is designed as an external plugin, not as a bundled Hermes
plugin. The upstream Hermes PR surface should stay focused on generic Feishu
adapter extension points, while this repository owns runner-specific queueing,
policy, worktree isolation, and operator documentation.

## License

MIT. See [LICENSE](LICENSE).
