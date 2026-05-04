# Upstream Hermes PR Plan

Keep the public plugin external. The Hermes Agent upstream PR should contain only
generic extension points that any plugin can use.

## PR 1: Feishu Card Action Hook

Scope:

- Let plugins respond to Feishu interactive card callbacks.
- Pass action value, operator identifiers, and message metadata to plugin hooks.
- Keep default behavior unchanged when no hook handles the callback.

Why:

This lets external plugins implement approval flows without patching the Feishu
adapter for each plugin.

## PR 2: Feishu Interactive Card Update API

Scope:

- Expose a small adapter method for updating an existing interactive card.
- Return structured success/failure results to callers.
- Add tests for update fallback behavior.

Why:

Long-running plugin tasks can update the same card through queued, running,
done, and failed states instead of sending separate final text messages.

## Not In Upstream

- Codex-specific queueing, worktree, policy, verification, or artifact code.
- Local repo aliases.
- Runtime configuration or smoke-test artifacts.
