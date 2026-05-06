# Installation

Hermes Agent Gateway is designed to be installed as a user plugin, outside the
Hermes Agent source tree.

## Install

```bash
hermes plugins install <owner>/hermes-agent-gateway
hermes plugins enable hermes-agent-gateway
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
cp ~/.hermes/plugins/hermes-agent-gateway/config.example.json \
  ~/.hermes/plugins/hermes-agent-gateway/config.json
```

Edit these fields first:

- `workspace_roots`: parent directories that may contain repositories.
- `repo_aliases`: friendly aliases accepted by `/agent runner=codex repo=...`.
- `approval_allowed_user_ids`: current Feishu/Lark adapter users allowed to
  approve write tasks.
- `approval_allowed_chat_ids`: current Feishu/Lark adapter chats allowed to
  trigger write tasks.

Do not put secrets in `config.json`. Use only non-secret environment overrides in
`codex_env`, such as proxy variables.
