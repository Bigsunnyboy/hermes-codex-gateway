# Runner Registry And A2A Posture Plan

This plan defines the next implementation phase after the Hermes Agent Gateway
hard-cut.

## Decision

Build an enabled-only static runner registry before adding more runners or A2A
endpoints.

Runtime support remains:

```text
enabled executable runners: codex
```

Claude Code, Qoder, and DeepSeek-TUI are future runner directions only. They
must not appear in runtime registry entries, public command help, public schema
descriptions, or quickstart/operations docs as supported runners until their
safe execution behavior is implemented and verified.

## Why This Comes Before A2A

A2A should map onto stable gateway concepts:

- task lifecycle;
- runner capabilities;
- channel source and actor references;
- artifacts;
- status and audit data.

The runner registry gives the future A2A adapter a truthful source of enabled
execution capabilities. The adapter must not advertise reserved runners through
AgentCard or task capabilities.

No A2A HTTP endpoint, streaming endpoint, subscribe flow, or compatibility
claim belongs in this phase.

## Why This Comes Before New Runners

New runners need per-runner permission mapping and official capability
validation. Adding them before the registry would mix three concerns:

- runner boundary extraction;
- external runner behavior research;
- security and governance mapping.

The first slice should move Codex behind the same boundary future runners will
use, while preserving current behavior.

## Required Runtime Shape

- `RunnerRegistry` is the single source of truth for enabled runner ids.
- Parser validates against enabled runner ids before queueing.
- Scheduler resolves runner factories through the registry.
- Task service repeats registry validation to defend against stale or forged
  queue records.
- Root plugin schema and runner construction use registry data.
- Public schema currently exposes only `codex` as supported.

## Documentation Posture

Public docs should describe the project as:

- a governed multi-channel gateway;
- multi-runner-capable in architecture;
- currently using Feishu/Lark as the first channel adapter;
- currently using Codex as the only enabled executable runner;
- A2A-capable in direction, with no current A2A endpoint claim.

Planning/reference docs may mention Claude Code, Qoder, DeepSeek-TUI, generic
CLI, and A2A milestones, but only with explicit reserved / not implemented /
deferred wording.

## Execution Scope

Touchpoints expected in the next implementation phase:

- `hermes_agent_gateway/runners/`
- `hermes_agent_gateway/command_parser.py`
- `hermes_agent_gateway/task_service.py`
- `hermes_agent_gateway/scheduler.py`
- root `__init__.py`
- `README.md`
- `OPERATIONS.md`
- `docs/RUNNER_CONTRACT.md`
- `docs/CHANNEL_CONTRACT.md`
- `docs/HERMES_AGENT_GATEWAY_ARCHITECTURE_PLAN.md`
- `docs/demo.md`
- `docs/install.md`
- `docs/feishu-commands.md`
- `docs/troubleshooting.md`
- `skills/agent-gateway-operator/SKILL.md`
- targeted tests for parser, registry, scheduler, task service, and plugin
  registration.

## Non-Goals

- No real Claude Code runner.
- No real Qoder runner.
- No real DeepSeek-TUI runner.
- No generic CLI runner.
- No A2A HTTP endpoint.
- No public schema/help entries for reserved runners.
- No disabled placeholder runners in runtime registry.
- No upstream Hermes core changes.
- No external coding-agent changes.

## Verification Summary

The implementation phase should pass:

- targeted parser/task/scheduler/plugin tests;
- full pytest;
- compileall;
- sanitize;
- public docs/schema grep gates;
- final verifier or code-reviewer approval.
