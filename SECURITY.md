# Security Policy

Hermes Agent Gateway runs local agent runner processes against user-selected
repositories. Treat it as an automation control plane, not as a secret store.

## Supported Use

- Keep `config.json`, runner auth files, Feishu app credentials, API keys, and
  project secrets outside this repository.
- Use `approval_allowed_user_ids` and `approval_allowed_chat_ids` before enabling
  write mode in shared chats.
- Use dedicated read-only or low-privilege credentials in projects that runners can
  access.
- Keep worktree and artifact roots under `~/.hermes/` or another private runtime
  directory.

## Reporting Issues

For vulnerabilities, open a private security advisory on GitHub if available.
If not available, open an issue with reproduction details but omit live tokens,
credentials, repository-private paths, and personal identifiers.
