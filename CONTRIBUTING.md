# Contributing

This repository is meant to stay installable as a standalone Hermes plugin.
Contributions should preserve that boundary.

## Development Checks

Run the focused test suite:

```bash
PYTHONPATH=. python -m pytest tests -q
```

Run the repository hygiene check before committing:

```bash
scripts/sanitize-check.sh
```

Run the official Docker install smoke test before release candidates:

```bash
scripts/docker-official-smoke.sh /path/to/hermes-codex-gateway
```

## Repository Rules

- Do not commit `config.json`, `.env`, Codex auth files, Feishu credentials,
  worktrees, queues, task artifacts, or generated caches.
- Keep plugin code independent of private Hermes internals where possible.
- Keep public examples generic. Use names like `example-repo`, not local project
  names.
- Prefer focused changes with tests for queue, routing, policy, runner, and
  delivery behavior.
