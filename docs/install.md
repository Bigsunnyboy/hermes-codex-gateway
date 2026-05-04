# Installation

Hermes Codex Gateway is designed to be installed as a user plugin, outside the
Hermes Agent source tree.

## Install

```bash
hermes plugins install <owner>/hermes-codex-gateway
hermes plugins enable hermes-codex-gateway
```

Restart the gateway after installation:

```bash
systemctl --user restart hermes-gateway.service
```

Use the service name that matches your environment if Hermes is managed by a
system-level unit instead of a user unit.

## Configure

Copy the example configuration:

```bash
cp ~/.hermes/plugins/hermes-codex-gateway/config.example.json \
  ~/.hermes/plugins/hermes-codex-gateway/config.json
```

Edit these fields first:

- `workspace_roots`: parent directories that may contain repositories.
- `repo_aliases`: friendly aliases accepted by `/codex repo=...`.
- `approval_allowed_user_ids`: Feishu users allowed to approve write tasks.
- `approval_allowed_chat_ids`: Feishu chats allowed to trigger write tasks.

Do not put secrets in `config.json`. Use only non-secret environment overrides in
`codex_env`, such as proxy variables.
