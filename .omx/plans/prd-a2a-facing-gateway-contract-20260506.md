# PRD: A2A-Facing Gateway Contract

Date: 2026-05-06
Status: consensus-approved planning artifact
Scope: planning for a future internal mapping contract; no implementation in this PRD

## Problem

Hermes Agent Gateway now has two stabilizing boundaries:

- `docs/RUNNER_CONTRACT.md` defines `codex` as the current only enabled
  executable runner, with no implicit default and no A2A endpoints.
- `docs/CHANNEL_CONTRACT.md` defines Feishu/Lark as current channel adapters,
  not Gateway Core or the only intended platform, and defines neutral
  actor/delivery/command shapes.

A future A2A adapter needs a small, truthful contract to map Gateway Core state
toward A2A concepts such as AgentCard, AgentCapabilities, AgentSkill, Message,
Task, TaskStatus, TaskState, Artifact, and streaming events. That contract must
not become an endpoint implementation, dependency decision, or public
compatibility claim.

## Desired Outcome

Create an execution-ready planning package for a later implementation phase
that defines the minimum internal mapping contract a future A2A adapter can use
without weakening Gateway Core governance.

The contract should make these boundaries explicit:

- A2A adapter owns protocol binding, HTTP+JSON endpoints, authentication
  presentation, transport errors, streaming/subscription delivery, and A2A
  version selection in a later phase.
- Gateway Core owns task creation, approval, risk policy, path guard,
  verification, artifacts, audit, and runner/channel capability truth.
- Runner capabilities are advertised only when enabled and verified through the
  runner registry; channel-facing context is derived from enabled channel
  identity plus neutral actor/delivery shapes unless a richer channel
  capability source is added later.
- Feishu/Lark channel internals and Codex runner internals must not leak into
  A2A-facing names.

## RALPLAN-DR

### Principles

1. Capability honesty: advertised A2A-facing capabilities are derived from
   enabled runner, channel, and gateway capabilities only.
2. Governance preservation: A2A-facing mapping cannot bypass approval, risk,
   path guard, verification, artifacts, or audit ownership in Gateway Core.
3. Adapter neutrality: internal mapping names must not expose Feishu/Lark event
   internals or Codex runner-private implementation details.
4. Endpoint restraint: this phase defines mapping contracts and docs only; it
   adds no route, SDK, dependency, server behavior, streaming behavior, or
   compatibility claim.
5. Version humility: exact wire-shape and endpoint conformance wait for the
   future selected A2A binding/version.

### Decision Drivers

1. Give a future A2A adapter a stable internal contract without forcing a
   transport decision now.
2. Keep public posture truthful: A2A is a direction, not implemented
   compatibility.
3. Preserve Gateway Core as the security and audit boundary while mapping
   queue, runner, channel, and artifact state toward protocol concepts.

### Options

#### Option A: Documentation-only mapping contract

Define the mapping in docs and planning artifacts only.

Pros:
- Lowest risk and fully matches the no-implementation constraint.
- Avoids committing code names before endpoint binding/version choices.
- Useful immediately for review and future execution scoping.

Cons:
- Future implementation still needs to translate prose into code.
- Mapping drift is possible until tests are written.

#### Option B: Internal mapping spec plus future test skeleton plan

Define the mapping in docs, PRD, and a test spec that names future test cases
and static gates, but still adds no runtime code.

Pros:
- Keeps this phase planning-only while making the next implementation slice
  testable.
- Gives reviewers concrete acceptance criteria for capability derivation,
  status mapping, artifact mapping, and forbidden claims.
- Aligns with the completed runner/channel contracts.

Cons:
- Slightly more planning surface than docs-only.
- Requires careful wording so planned test names do not imply existing code.

#### Option C: Add mapping helper module now, without endpoints

Implement internal Python helpers for A2A-facing shapes while deferring routes.

Pros:
- Locks mapping behavior with tests sooner.
- Reduces ambiguity for the endpoint phase.

Cons:
- Violates the user's planning-only constraint for this phase.
- Risks freezing names before A2A binding/version and auth choices are selected.

### Recommendation

Choose Option B. Produce a PRD, test spec, and docs plan that define a minimal
future internal mapping contract and verification path, while explicitly
deferring all code, endpoints, SDKs, dependencies, transport behavior, and
compatibility claims.

## Future Internal Contract Surface

The later implementation phase should add a small internal contract boundary,
tentatively named `A2AGatewayContract`, only after this plan is approved for
execution. The names below are planning terms, not existing APIs.

### Capability View

Future A2A-facing capability views must derive from:

- `enabled_runner_ids()` and `RunnerDefinition.capabilities`;
- enabled channel identity and neutral actor/delivery context from the channel
  boundary, currently Feishu/Lark as adapters;
- protocol capability candidates selected by a later binding/version plan;
- gateway-owned governance metadata for approval, risk blocking, verification
  commands, allowed path guards, artifacts, audit, and session resume where
  enabled by the runner.

The capability view must not:

- advertise disabled, reserved, or planning-only runners;
- imply an implicit default runner;
- claim A2A endpoint, streaming, push notification, or compatibility support;
- expose runner-private command, permission, callback, or queue names.
- present gateway governance metadata as A2A `AgentCapabilities`.

### Skill View

Future AgentSkill-like mapping should describe gateway-supported work types,
not product-specific runner branding:

- read/planning task when at least one enabled runner supports read;
- approved write task when at least one enabled runner supports write and
  Gateway Core approval/risk/path guard/verification controls remain active;
- resume/session continuation only when enabled runner capabilities support it.

### Message Envelope

Future Message-like inbound mapping should normalize adapter input to the same
gateway command payload used by the channel boundary:

- `runner`;
- `repo`;
- `path`;
- `mode`;
- `workspace_id`;
- `agent_session_id`;
- `verify_commands`;
- `allowed_paths`;
- `prompt`;
- actor and delivery metadata when present.

The A2A adapter may own protocol-specific message ids and parts in a later
endpoint phase, but Gateway Core should receive only gateway-neutral command
fields.

### Task Status View

Future Task/TaskStatus/TaskState-like mapping must be derived from queue and
task-service status, not from channel or runner internals:

- `QUEUED`: submitted semantic; accepted by Gateway Core and awaiting scheduler
  claim;
- `RUNNING`: working semantic; runner execution is in progress;
- `APPROVAL_REQUIRED`: input-required semantic; blocked on Gateway Core
  approval;
- `REJECTED`: rejected semantic with approval metadata;
- `BLOCKED`: rejected-or-failed semantic with risk metadata; exact protocol
  representation is deferred;
- `DONE`: completed semantic;
- `FAILED`: failed semantic caused by runner, verification, guard, worktree, or
  gateway error.

Exact A2A `TaskState` enum values are deferred to the future endpoint binding
phase. This phase should record semantic intent only and identify
`APPROVAL_REQUIRED`, `REJECTED`, and `BLOCKED` as states needing explicit
protocol mapping or gateway-specific metadata later.

Current path allowlist violations are post-run gateway policy failures and map
to `FAILED` with error metadata unless a later status model explicitly changes
that behavior.

### Artifact View

Future Artifact-like mapping should reference Gateway Core artifact records and
task output locations, including:

- task JSON;
- bounded runner stdout/stderr artifacts;
- before/after git status, diff stat, and diff artifacts;
- verification results;
- audit/risk metadata already captured by Gateway Core.

Protocol-facing artifact views must sanitize `task_record` content by stripping
or replacing raw absolute `project_path`, `execution_path`, `artifact_dir`,
runner command paths, and private filesystem paths.

The A2A adapter must not own artifact persistence or bypass sensitive file
handling and artifact redaction decisions.

### Event View

Future streaming-event-like mapping may describe Gateway Core lifecycle changes
as candidate events, but this planning phase does not add streaming,
subscription, push notification, or event transport behavior.

Candidate event semantics for later phases:

- task accepted;
- task approval required;
- task rejected;
- task running;
- task blocked;
- task artifact available;
- task completed;
- task failed.

## Functional Requirements For The Future Implementation Phase

- Add a docs-backed internal mapping contract before adding any A2A endpoint.
- Derive capability and skill views only from enabled runner capabilities,
  enabled channel identity plus neutral actor/delivery context, and
  gateway-owned control capabilities.
- Preserve explicit runner requirement; do not introduce an implicit runner
  default.
- Preserve Gateway Core ownership of approval, risk, path guard, verification,
  artifacts, and audit.
- Keep A2A-facing names neutral; avoid Feishu/Lark and Codex private names.
- Document unresolved A2A binding/version questions as follow-ups, not hidden
  assumptions.

## Non-Goals

- No A2A HTTP+JSON endpoint.
- No route, controller, server, SDK, dependency, or protocol client.
- No streaming, subscribe, push notification, or event transport behavior.
- No compatibility or conformance claim.
- No new channel adapter.
- No new runner.
- No changes to scheduler, queue behavior, task creation, runner invocation,
  delivery, approval callbacks, path guard, verification, artifacts, or audit.

## Acceptance Criteria

- PRD names the minimum future mapping surfaces: capability, skill, message,
  task status, artifact, and event views.
- PRD states that capability advertisement is derived only from enabled runner
  capabilities, enabled channel identity plus neutral actor/delivery context,
  and gateway-owned control capabilities.
- PRD explicitly preserves Gateway Core ownership of approval, risk, path guard,
  verification, artifacts, and audit.
- PRD explicitly defers A2A endpoints, SDKs, dependencies, streaming,
  subscriptions, push notifications, auth binding, and compatibility claims.
- Test spec includes future unit/static/doc gates for capability derivation,
  status mapping, artifact mapping, and forbidden public claims.
- Docs plan identifies which public docs should change and which planning docs
  may mention A2A with future/deferred wording.
- No implementation files are changed as part of this planning phase.

## ADR

Decision:
- Define an internal A2A-facing Gateway Contract as a planning package first,
  using Option B: PRD plus test spec plus docs plan, with no runtime code.

Drivers:
- A future A2A adapter needs stable gateway-neutral mapping inputs.
- Capability advertisement must remain truthful and derived from enabled
  gateway capabilities.
- Gateway Core governance must remain the security and audit boundary.

Alternatives considered:
- Documentation-only mapping contract: lower effort but weaker testability for
  the next phase.
- Mapping helper implementation now: clearer behavior but violates the
  planning-only constraint and may freeze names too early.

Why chosen:
- Option B creates enough specificity for execution and review while fully
  respecting the no-endpoint, no-code, no-compatibility-claim constraint.

Consequences:
- The next implementation phase can start from concrete tests and docs gates.
- Exact A2A `TaskState`, auth, transport, and streaming choices remain open.
- Public posture must continue saying future A2A direction, not implemented
  compatibility.

Follow-ups:
- Select the A2A binding/version before endpoint implementation.
- Decide how `APPROVAL_REQUIRED`, `REJECTED`, and `BLOCKED` map to A2A task
  state or gateway-specific metadata.
- Decide whether the first endpoint phase supports streaming/subscription or
  explicitly defers it.
- Define authentication/security scheme presentation for any future AgentCard.

## Execution Handoff Guidance

Available agent types:
- `executor`: write docs/tests/code when execution is approved.
- `test-engineer`: turn this test spec into concrete tests.
- `architect`: review boundary ownership and protocol mapping tradeoffs.
- `critic`: challenge compatibility-claim wording and acceptance criteria.
- `verifier`: confirm no endpoints/runtime behavior were added.
- `code-reviewer`: review the final implementation phase if code is later
  approved.
- `writer`: perform docs posture cleanup.

Ralph path:
- Use one `executor` with medium reasoning for a conservative docs/test/code
  slice, then `verifier` with high reasoning.
- Stop after mapping docs/tests are green and no endpoint/runtime behavior is
  present.

Team path:
- Lane 1, `writer`, high reasoning: docs contract and public posture cleanup.
- Lane 2, `test-engineer`, medium reasoning: mapping and static gate tests.
- Lane 3, `architect`, high reasoning: boundary review before implementation
  merges.
- Lane 4, `verifier`, high reasoning: final no-endpoint/no-claim verification.

Suggested launch hints:
- `$ralph "Implement the A2A-facing Gateway Contract planning-approved mapping slice only; no endpoints, SDKs, dependencies, streaming, or compatibility claims."`
- `$team "Implement the A2A-facing Gateway Contract mapping/docs/test slice with separate writer, test-engineer, architect, and verifier lanes; no endpoints or runtime protocol behavior."`

Team verification path:
- Run focused mapping tests created from the test spec.
- Run full pytest and compileall.
- Run static grep gates for forbidden endpoint routes, A2A compatibility claims,
  reserved runner advertisement, and Feishu/Lark or Codex private leakage.
- Confirm changed files do not add new dependencies, routes, SDK imports, or
  runtime behavior.
