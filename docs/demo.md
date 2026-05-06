# Demo Script

This short script is meant for a 60-90 second screen recording or live demo.
It shows the plugin as a governed chat-to-agent workflow, not as a raw remote
shell.

## Setup Shot

Show the repository and the installed plugin:

```bash
hermes plugins list
hermes plugins enable hermes-agent-gateway
```

Show the non-secret config fields that matter:

```json
{
  "workspace_roots": ["/home/projects"],
  "repo_aliases": {
    "demo": "/home/projects/demo-repo"
  },
  "approval_allowed_user_ids": ["ou_example"],
  "approval_allowed_chat_ids": ["oc_example"]
}
```

Do not show API keys, Feishu secrets, runner auth files, or private project
credentials.

## Read-Only Flow

In Feishu/Lark, send:

```text
/agent runner=codex repo=demo mode=read workspace=demo-read-001
Summarize this repository structure and identify the test command. Do not modify files.
```

Narration:

```text
The chat command becomes a Hermes plugin task. Read mode runs without approval
because it is sandboxed for analysis, and the result comes back to the same chat.
```

Show:

- The queued task.
- The agent run.
- The returned summary or result card.

## Approved Write Flow

In Feishu/Lark, send:

```text
/agent runner=codex repo=demo mode=write workspace=demo-docs-001 verify=file:docs/demo-note.md allow=docs/demo-note.md
Create docs/demo-note.md with a short note explaining that the demo write path works.
```

Narration:

```text
Write mode requires approval. The task also has an allowlist, so the selected runner may only
change docs/demo-note.md, and verify runs before success is reported.
```

Show:

- Approval card or text fallback.
- The approval action.
- Worktree creation.
- Verification result.
- Final chat response.

## Safety Close

End with the control model:

```text
The important part is the boundary: Feishu starts the workflow, Hermes owns the
plugin and wake gate, the selected runner works in an isolated worktree, and success requires
the configured policy plus verification.
```

Point viewers to:

- [README.md](../README.md)
- [docs/install.md](install.md)
- [docs/safety-model.md](safety-model.md)
- [docs/feishu-commands.md](feishu-commands.md)
