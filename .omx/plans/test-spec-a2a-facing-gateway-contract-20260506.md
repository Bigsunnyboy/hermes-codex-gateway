# Test Spec: A2A-Facing Gateway Contract

Date: 2026-05-06
Status: consensus-approved planning artifact
Scope: planning for tests in a future implementation phase; no tests are added
by this planning artifact

## Scope

This spec defines the verification shape for a future internal mapping contract
that maps Gateway Core state toward A2A concepts without adding endpoints,
dependencies, streaming behavior, or compatibility claims.

It covers:

- capability and skill view derivation;
- message envelope normalization;
- queue/task status semantic mapping;
- artifact reference mapping;
- event semantic mapping for later streaming support;
- public documentation posture gates.

It does not cover:

- real A2A HTTP+JSON endpoints;
- protocol conformance tests;
- streaming, subscribe, push notification, or cancellation endpoints;
- SDK integration;
- new runners or new channel adapters.

## Unit Test Plan For Future Implementation

### Capability View

Required assertions:

- enabled runner ids are read from `enabled_runner_ids()`;
- no disabled, reserved, or planning-only runner appears in advertised
  capabilities;
- `RunnerCapabilities.supports_read` controls read/planning skill exposure;
- `RunnerCapabilities.supports_write` controls write skill exposure;
- `RunnerCapabilities.supports_resume` controls resume/session exposure;
- `supports_json_output`, `supports_permission_mode`, and
  `dangerous_modes_disabled` are represented only as truthful internal
  capability facts, not protocol compatibility claims;
- gateway governance metadata is not presented as A2A `AgentCapabilities`;
- missing or unknown runner ids are not silently converted to `codex`.

### Skill View

Required assertions:

- read task skill is present only when at least one enabled runner supports
  read;
- write task skill is present only when at least one enabled runner supports
  write and gateway approval/risk/path guard/verification ownership remains
  described;
- resume skill is present only when at least one enabled runner supports resume;
- skill labels are gateway-neutral and do not expose runner-private command or
  permission names.

### Message Envelope

Required assertions:

- future A2A-like input normalizes to gateway command fields:
  `runner`, `repo`, `path`, `mode`, `workspace_id`, `agent_session_id`,
  `verify_commands`, `allowed_paths`, and `prompt`;
- runner remains explicit and required;
- channel actor and delivery metadata use neutral channel boundary concepts
  when present;
- Feishu/Lark raw event fields are not required by the mapping contract.

### Task Status View

Required assertions:

- `QUEUED` maps to accepted/queued semantic intent;
- `RUNNING` maps to running semantic intent;
- `APPROVAL_REQUIRED` maps to approval-needed semantic intent and is flagged as
  requiring explicit future A2A binding treatment;
- `REJECTED` maps to rejected semantic intent and is flagged as requiring
  explicit future A2A binding treatment;
- `BLOCKED` maps to pre-run risk/governance-blocked semantic intent and is
  flagged as requiring explicit future A2A binding treatment with risk
  metadata;
- `DONE` maps to completed semantic intent;
- `FAILED` maps to failed semantic intent;
- current path allowlist violations map to `FAILED` with gateway policy error
  metadata unless a later status model explicitly changes that behavior;
- unknown statuses fail closed rather than being advertised as completed.

Exact A2A `TaskState` enum values should be tested only after the future
endpoint binding/version is selected.

### Artifact View

Required assertions:

- task JSON can be referenced as a gateway-owned task artifact;
- bounded stdout/stderr artifacts can be referenced without exposing runner
  internals as public protocol fields;
- before/after git status, diff stat, and diff artifacts remain gateway-owned;
- verification results remain gateway-owned;
- artifact mapping does not read sensitive files directly or bypass artifact
  persistence.
- sanitized `task_record` output strips or replaces raw absolute
  `project_path`, `execution_path`, `artifact_dir`, runner command paths, and
  private filesystem paths.

### Event Semantics

Required assertions:

- lifecycle event semantics can be derived from Gateway Core status changes;
- event mapping is inert unless a future transport layer consumes it;
- no streaming, subscribe, push notification, or route behavior is introduced by
  the internal mapping contract.

## Static Gates For Future Implementation

### No Endpoint Or Transport Surface

Suggested command:

```bash
rg -n "message:send|message/send|message:stream|message/stream|tasks/get|tasks/cancel|tasks/resubscribe|tasks/|/tasks|/v1/message:send|/v1/tasks|subscribe|pushNotification|pushNotificationConfig|agent/getAuthenticatedExtendedCard|AgentCard|A2A-compatible|a2a-compatible|A2A compatibility" \
  hermes_agent_gateway __init__.py README.md OPERATIONS.md docs skills
```

Expected:
- no matches that claim implemented endpoint behavior or compatibility;
- planning/reference docs may mention A2A concepts only with future/deferred or
  not-implemented wording.

### No New Dependencies

Suggested command:

```bash
git diff -- pyproject.toml requirements*.txt setup.cfg setup.py
```

Expected:
- no A2A SDK, HTTP framework, streaming, or protocol dependency in the mapping
  contract phase.

### No Runner Or Channel Leakage

Suggested command:

```bash
rg -n "CodexCliRunner|codex_executable|feishu_router|event\\.message_id|event\\.source|chat_id|approval_card" \
  docs/A2A* docs/*A2A* .omx/plans/*a2a*
```

Expected:
- no runner-private or raw Feishu/Lark fields in future A2A-facing public
  contract names;
- compatibility field names may appear only when explicitly documenting
  existing queue serialization boundaries.
- if a future A2A-facing Python module is added, include only that module in
  this gate rather than scanning existing private runner/channel
  implementation files where those strings are legitimate.

### Capability Truthfulness

Suggested command:

```bash
rg -n "Claude Code|Qoder|DeepSeek-TUI|generic CLI|claude-code|qoder|deepseek-tui|default runner|A2A-compatible|full A2A" \
  README.md OPERATIONS.md docs skills __init__.py hermes_agent_gateway
```

Expected:
- no runtime or public docs claim support for reserved runners, implicit runner
  defaults, or A2A compatibility.

## Standard Verification For Future Implementation

Run after any later implementation phase:

```bash
PYTHONPATH=. python3 -m pytest tests -q
python3 -m compileall -q hermes_agent_gateway
scripts/sanitize-check.sh
git diff --check
```

Focused tests should be added for the mapping module or docs validation files
chosen in that later phase.

## Review Gates

- Architect confirms A2A adapter, channel adapter, runner registry, and Gateway
  Core ownership boundaries remain separate.
- Critic confirms acceptance criteria are testable and alternatives are fairly
  represented.
- Verifier confirms no endpoint, SDK, dependency, streaming behavior, or
  compatibility claim was introduced.
- Code reviewer is required if the later phase adds Python mapping helpers.

## Residual Risks

- Exact A2A `TaskState` values may change with the selected binding/version;
  keep semantic mapping separate until implementation.
- `APPROVAL_REQUIRED`, `REJECTED`, and `BLOCKED` may need extension metadata or
  a carefully chosen A2A state mapping.
- Public docs can accidentally overstate future A2A direction; grep gates should
  be part of verification.
