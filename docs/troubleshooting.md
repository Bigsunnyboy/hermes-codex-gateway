# Troubleshooting

## Command Queues But Never Runs

Check that the worker cron exists:

```text
ensure_agent_worker_cron
```

Then inspect the queue directory configured by `artifact_root.parent/agent_queue`.

## Runner Cannot Reach the API

Set non-secret proxy variables in `codex_env`, for example:

```json
{
  "codex_env": {
    "HTTPS_PROXY": "http://127.0.0.1:7890",
    "HTTP_PROXY": "http://127.0.0.1:7890"
  }
}
```

Do not commit this local `config.json`.

## Write Task Fails After Successful Runner Run

Check the final error. If it says changes happened outside `allow=`, either the
prompt changed extra files or the worktree had pre-existing untracked files.
Use a fresh workspace id for smoke tests.

## Approval Card Does Not Update

The plugin falls back to text delivery when the active Hermes Feishu adapter does
not expose card callback or card update support. Upgrade Hermes Agent or use the
manual `/agent approve <task_id>` fallback.
