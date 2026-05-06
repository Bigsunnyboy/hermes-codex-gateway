# A2A-Facing Gateway Contract Plan

This plan defines the internal gateway contract that a future A2A adapter can
map onto. It is not an endpoint implementation and it is not an A2A
compatibility claim.

## Decision

Define an A2A-facing internal mapping contract over existing Gateway concepts:

- enabled runner registry;
- neutral channel actor and delivery references;
- queue task lifecycle;
- risk and approval governance;
- artifact and verification records.

The future adapter may translate this contract into A2A protocol objects, but
Gateway Core must not depend on A2A transport, Feishu/Lark platform details, or
runner-specific invocation flags.

## Current Truth Sources

- Runner capability truth comes from `hermes_agent_gateway/runners/registry.py`.
  The current only enabled executable runner id is `codex`.
- Channel provenance comes from `hermes_agent_gateway/channel_boundary.py`.
  Feishu/Lark are current channel adapters, not Gateway Core.
- Lifecycle truth comes from `hermes_agent_gateway/queue.py` and task result
  JSON written by `hermes_agent_gateway/task_service.py`.
- Artifact truth comes from the artifact directory, including stdout, stderr,
  diff, verification results, and `task.json`.

## Contract Surfaces To Define

The first mapping-only slice is implemented in
`hermes_agent_gateway/a2a_gateway_contract.py`. The next internal slice connects
that contract to real `FileTaskQueue` records, `task.json`, and bounded
artifact previews. Both slices remain internal contract plumbing only.

### Gateway Agent Descriptor

Purpose:
- produce the internal data a future AgentCard generator would consume;
- avoid serving or signing an AgentCard in this phase.

Fields:
- gateway identity and description;
- supported input and output media types for the gateway contract;
- enabled runner ids and their `RunnerCapabilities`;
- supported task modes derived from gateway policy and runner capability;
- gateway governance metadata such as approval, path guard, verification, and
  artifact capture;
- protocol capability candidates, separated from governance metadata, with
  streaming, subscribe, push notifications, extended agent card, signed card,
  additional runners, and public endpoints marked unsupported.

Rule:
- never include reserved runners or unimplemented protocol capabilities.
- never present gateway governance metadata as A2A `AgentCapabilities`; exact
  protocol capability fields are selected only in a later binding/version plan.

### Gateway Message Intake

Purpose:
- define how a future A2A `Message` becomes the current neutral task payload.

Mapping:
- user text parts -> `prompt`;
- metadata runner -> `runner`, validated by the enabled runner registry;
- metadata repository/path/workspace/mode/verify/allow -> current task payload
  fields after existing validation;
- message actor information -> `ChannelActor(channel="a2a", actor_id=...)`;
- message context/task references -> adapter-owned metadata, not runner session
  ids;
- unsupported parts or modes -> validation error in the future adapter, not a
  partial Gateway task.

Rule:
- the adapter may enrich a neutral payload, but Gateway Core still owns risk,
  approval, queueing, execution, verification, artifacts, and audit.

### Gateway Task View

Purpose:
- define how a gateway queue/task record becomes a protocol-facing task view.

Mapping:

| Gateway state | A2A-facing internal state | Notes |
| --- | --- | --- |
| `QUEUED` | submitted semantic | Accepted but not yet executing. |
| `RUNNING` | working semantic | Runner execution has been claimed. |
| `APPROVAL_REQUIRED` | input-required semantic | Requires explicit approval before write execution; exact protocol representation is deferred. |
| `DONE` with success | completed semantic | Include artifacts and verification summary. |
| `FAILED` | failed semantic | Include bounded error metadata and failed gate. |
| `REJECTED` | rejected semantic | Approval was explicitly denied; include approval metadata. |
| `BLOCKED` | rejected or failed semantic | Risk policy blocked execution before queue/run; future binding plan must choose representation and include risk metadata. |

Rule:
- this table is a semantic target only. The final A2A enum spelling and error
  representation must be selected from the chosen A2A binding during endpoint
  implementation.

### Gateway Artifact View

Purpose:
- expose stable artifact categories without leaking filesystem layout or runner
  internals.

Artifact categories:
- `summary`: final task status and user-facing result text;
- `stdout`: bounded runner stdout;
- `stderr`: bounded runner stderr;
- `diff`: captured workspace diff, when present;
- `verification`: verify command results;
- `task_record`: sanitized `task.json` metadata;
- `audit`: runner id, channel provenance, actor reference, approval, risk, and
  path guard outcome.

Rule:
- future protocol artifacts should carry references or bounded text parts; they
  must not expose sensitive paths, raw secrets, or unbounded runner output.
- sanitized task records must strip or replace raw absolute `project_path`,
  `execution_path`, `artifact_dir`, runner command paths, and any private
  filesystem paths before becoming protocol-facing artifacts.

### Gateway Event View

Purpose:
- prepare for future streaming/push without implementing it now.

Event kinds:
- `task_submitted`;
- `task_working`;
- `approval_required`;
- `artifact_available`;
- `task_completed`;
- `task_failed`;
- `task_rejected`;
- `task_blocked`.

Rule:
- events are planning vocabulary only in this phase. No SSE, subscribe,
  webhooks, push notification config, or background event bus is added.

## Non-Goals

- No A2A HTTP+JSON, JSON-RPC, gRPC, or custom binding endpoint.
- No `/.well-known/agent-card.json` or `GET /extendedAgentCard` behavior.
- No `POST /message:send`, `POST /message:stream`, task listing, cancel,
  subscribe, push notification, or streaming endpoint.
- No A2A SDK dependency.
- No public compatibility claim.
- No new channel adapter.
- No new runner.
- No disabled placeholder runners in the runtime registry.
- No bypass of approval, risk, path guard, verification, artifact, or audit
  controls.

## Documentation Posture

Public and operator-facing docs may say:

```text
Hermes Agent Gateway has an A2A-facing internal contract plan. It does not yet
serve A2A protocol endpoints or claim A2A compatibility.
```

They must not:

- describe the gateway as protocol-compatible before endpoint conformance is
  implemented and verified;
- describe any A2A message endpoint as currently supported;
- describe any AgentCard as currently exposed;
- describe Claude Code, DeepSeek-TUI, or Qoder as enabled runners.

## Implementation Handoff

The mapping-only slice has already been implemented. The next execution handoff
is the larger real-record/artifact projection batch:

1. Build sanitized internal task views from queue records.
2. Read `task.json` and allowlisted artifact files into bounded previews.
3. Preserve queue `task_id` and queue `status` as authoritative.
4. Keep execution ids, artifact paths, runner command paths, and raw filesystem
   paths sanitized as metadata.
5. Do not add transport routes, server registration, public schemas, or SDK
   dependencies.

## Verification Expectations

- Unit tests prove reserved runners and unsupported protocol capabilities are
  not advertised.
- Unit tests prove each current gateway queue state maps to exactly one internal
  A2A-facing state.
- Unit tests prove `APPROVAL_REQUIRED` remains a governance hold and cannot
  execute through adapter input alone.
- Static grep proves no A2A endpoints, protocol compatibility claims, disabled
  runners, or new public route names were added.
- Full test suite remains green after implementation.

## Superseded Wording

Older architecture notes used endpoint names as a minimum A2A adapter target.
This plan narrows the next phases: define the internal mapping contract first,
then connect it to real queue/task/artifact records. Endpoint names remain
protocol research references only until a later endpoint implementation plan
selects a binding, version, auth model, and conformance test path.
