# Hermes Codex Gateway Operations

This file is for operators running the gateway in a real Hermes installation.

## Runtime Layout

The plugin should live in the Hermes user plugin directory:

```text
~/.hermes/plugins/hermes-codex-gateway
```

It should not be copied into a Hermes source checkout's bundled plugin
directory unless Hermes maintainers explicitly decide to ship it in-tree.

Runtime state belongs outside this repository:

```text
~/.hermes/agent_queue
~/.hermes/agent_tasks
~/.hermes/worktrees
~/.hermes/worktree_archives
~/.hermes/agent_sessions
~/.hermes/codex_home
```

Never commit those directories.

## Install Or Update

```bash
hermes plugins install <owner>/hermes-codex-gateway
hermes plugins enable hermes-codex-gateway
systemctl restart hermes-gateway.service
```

If you update the repository manually, copy only the plugin source and example
config. Preserve any existing runtime `config.json`.

## Worker Cron

Run once after install:

```text
ensure_codex_worker_cron
```

The created cron job uses `~/.hermes/scripts/codex_queue_worker_wake.py`.
Empty queues return `{"wakeAgent": false}` and Hermes skips the agent run.
Non-empty queues wake the plugin tool path so the live Feishu adapter can update
RUNNING/DONE/FAILED lifecycle cards.

The worker prompt includes a computed `gateway-worker-prompt:<hash>` prefix so
cron repair can detect stale prompt versions even when Hermes only returns a
shortened `prompt_preview`.

## Smoke Test

Use a disposable git repository first:

```text
/codex path=/home/projects/example mode=write workspace=publish-smoke-001 verify=file:publish-smoke.txt allow=publish-smoke.txt
Create publish-smoke.txt with the exact text: publish smoke ok. Do not modify any other file.
```

Expected result:

- Approval card appears.
- Approve button queues the task.
- The same card moves through RUNNING to DONE.
- Only `publish-smoke.txt` changes inside the managed worktree.

## Troubleshooting

- No response to `/codex`: confirm the plugin is enabled and the gateway was restarted.
- Queue does not drain: run `ensure_codex_worker_cron` and inspect `~/.hermes/agent_queue`.
- Codex cannot reach the API: configure non-secret proxy variables in `codex_env`.
- Card update unavailable: text approval and final delivery should still work if the Hermes Feishu adapter lacks card update hooks.
- Unexpected write failure: inspect task artifact `after_status.txt` and compare with the `allow=...` list.

## Safety Rules

- Use `mode=read` for analysis.
- Use `mode=write` only with approval, `allow=...`, and `verify=...`.
- Do not target credentials, `.env`, `auth.json`, `credentials*`, `*.key`, or secret files.
- Do not use this plugin to edit Hermes governance directories such as `.git`,
  `.codex`, `.omx`, `.hermes`, or the plugin's own source.
