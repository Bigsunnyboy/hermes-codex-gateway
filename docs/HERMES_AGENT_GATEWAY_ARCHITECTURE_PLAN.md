# Hermes Agent Gateway Architecture Plan

> Version: v0.1 planning baseline
> Date: 2026-05-06
> Scope: Upgrade the current repository into a general Hermes Agent Gateway.

## Executive Decision

The current repository should be replanned as **Hermes Agent Gateway**.

This is a hard direction change, not a compatibility migration. The project has
not formally launched, so there is no requirement to preserve the old Codex-only
public surface. Any previous references to keeping `/codex`, Codex-specific tool
names, Feishu-specific core fields, or compatibility aliases are treated as old
brainstorming notes and are not part of the target plan.

The target product is not a Codex gateway, not a Feishu gateway, and not an A2A
gateway only. It is a governed Hermes gateway for delegating tasks to external
agents through neutral channel, task, runner, artifact, approval, and audit
contracts.

```text
User / External System / Automation Trigger
        -> Channel Adapter Layer
        -> Hermes Runtime / Plugin Layer
        -> Gateway API Layer
        -> Gateway Core
        -> Runner Contract Layer
        -> Runner Implementations
```

## Principles

1. Public identity is agent-generic.
   No public package, tool, command, card, docs, or task schema should encode
   Codex, Feishu, Claude Code, Qoder, DeepSeek-TUI, or any other specific
   platform as the product identity.

2. Channel is not core.
   Feishu/Lark is one channel adapter. Future channels may include CLI, REST,
   Web, Slack, Telegram, Cron, and A2A.

3. Runner is not core.
   Codex is one runner implementation. Future runners can include Claude Code,
   OpenCode, Qoder, Trae, DeepSeek-TUI, generic CLI, HTTP/SSE runtimes, or
   future coding agents.

4. A2A is an adapter, not the rewrite reason.
   The gateway should be A2A-capable in direction only for now. It should
   implement a minimum A2A adapter later, and support streaming/subscribe after
   the core contracts stabilize.

5. Governance is the stable center.
   Queueing, policy, approval, worktree isolation, changed-path allowlists,
   verification, artifacts, notification, and audit remain in Gateway Core.

6. No compatibility aliases.
   Since the project is not formally launched, hard-cut the public surface now.
   Do not keep `/codex` as a shortcut and do not dual-register old tool names.

## Naming Decision

Recommended product name:

```text
Hermes Agent Gateway
```

Recommended repository / plugin id:

```text
hermes-agent-gateway
```

Recommended Python package:

```text
hermes_agent_gateway
```

Rejected names:

| Name | Reason |
|---|---|
| `Hermes Codex Gateway` | Binds the product to one runner. |
| `Hermes Feishu Gateway` | Binds the product to one channel. |
| `Hermes Local Agent Gateway` | Implies local-only execution and conflicts with future remote runners. |
| `Hermes A2A Coding Agent Gateway` | Overstates A2A Protocol completeness before it exists. |
| `Hermes Coding Agent Gateway` | Better than Codex-specific naming, but narrower than the intended general agent gateway identity. |

The implementation can still include coding-agent-focused runners first, but
the public architecture should not prevent future non-coding agent delegation.

## Public Surface Hard Cut

The target public surface is:

| Old surface | Target surface |
|---|---|
| `hermes-codex-gateway` | `hermes-agent-gateway` |
| `hermes_local_agent_gateway` | `hermes_agent_gateway` |
| `/codex ...` | `/agent ...` |
| `hermes_codex_action` | `hermes_agent_action` |
| `create_codex_task` | `create_agent_task` |
| `submit_codex_command` | `submit_agent_command` |
| `run_next_codex_task` | `run_next_agent_task` |
| `deliver_codex_task_result` | `deliver_agent_task_result` |
| `ensure_codex_worker_cron` | `ensure_agent_worker_cron` |
| `get_codex_task_status` | `get_agent_task_status` |
| `approve_codex_task` | `approve_agent_task` |
| `manage_codex_workspace` | `manage_agent_workspace` |
| `codex_session_id` | `agent_session_id` |
| `codex_queue_task_id` | `agent_queue_task_id` |
| `codex-queue-worker` | `agent-queue-worker` |
| `codex_queue_worker_wake.py` | `agent_queue_worker_wake.py` |
| `skills/codex-gateway-operator` | `skills/agent-gateway-operator` |

Forbidden after the cut:

- `/codex` parsing or fallback routing.
- Public tools containing `codex`.
- Public schemas containing `codex_session_id`.
- Card payloads containing `hermes_codex_action`.
- Docs that describe the product as Codex-specific or Feishu-specific.
- Dual-registration of old and new tool names.

Allowed exception:

- Runner implementation internals may use runner-specific names, for example a
  private `CodexRunner` module. Runner-specific names must not leak into Gateway
  Core, public task schemas, public tool names, or channel contracts.

## Target Architecture

### Channel Adapter Layer

Purpose:

- Convert external events into neutral gateway commands.
- Convert gateway notifications into channel-specific messages.

Examples:

- `channels/feishu.py`
- `channels/cli.py`
- `channels/rest.py`
- `channels/a2a.py`
- `channels/cron.py`

Channel-specific fields such as Feishu `open_id`, `chat_id`, and card callback
payloads must be translated before entering Gateway Core.

### Hermes Runtime / Plugin Layer

Purpose:

- Register Hermes plugin tools, hooks, and skills.
- Wire scheduler entrypoints.
- Keep Hermes plugin mechanics separate from domain logic.

Examples:

- `hermes_plugin/tools.py`
- `hermes_plugin/hooks.py`
- `hermes_plugin/schemas.py`

### Gateway API Layer

Purpose:

- Define the public tool/API commands:
  - `create_agent_task`
  - `submit_agent_command`
  - `run_next_agent_task`
  - `deliver_agent_task_result`
  - `ensure_agent_worker_cron`
  - `get_agent_task_status`
  - `approve_agent_task`
  - `manage_agent_workspace`

This layer should be channel-neutral and runner-neutral.

### Gateway Core

Purpose:

- Task lifecycle.
- Queue.
- Policy.
- Approval.
- Worktree isolation.
- Path guard.
- Verification gate.
- Artifact capture.
- Audit trail.
- Notification orchestration.

Existing modules such as queue, policy, worktree, verify, artifacts, delivery,
scheduler, sessions, and risk policy are valuable seed assets. They should be
renamed and moved behind neutral core contracts rather than rewritten.

### Runner Contract Layer

Purpose:

- Normalize how external agents are invoked.
- Map gateway modes to runner-specific permission models.
- Normalize runner output into a common `RunnerResult`.

The core rule is simple:

```text
Gateway Core owns governance.
Runner owns invocation and output normalization.
```

### Runner Implementations

Initial implementation can be based on the current Codex subprocess runner, but
it should be one private runner implementation, not the gateway identity.

Future runners:

- Codex runner.
- Claude Code runner.
- OpenCode runner.
- Qoder runner.
- Trae runner.
- DeepSeek-TUI runner.
- Generic CLI runner.
- HTTP/SSE runtime runner.

## Domain Model

### GatewayTask

```python
@dataclass
class GatewayTask:
    task_id: str
    created_at: str
    updated_at: str
    actor: ActorRef
    source: SourceRef
    repo: str
    workspace: str | None
    mode: Literal["read", "write"]
    runner: str
    prompt: str
    allow_paths: list[str]
    verify_commands: list[str]
    status: TaskStatus
    approval: ApprovalState | None
    metadata: dict[str, Any]
```

### ActorRef

```python
@dataclass
class ActorRef:
    actor_id: str
    display_name: str | None
    channel: str
    roles: list[str]
```

### SourceRef

```python
@dataclass
class SourceRef:
    channel: str
    conversation_id: str | None
    message_id: str | None
    callback_ref: str | None
```

### TaskStatus

```python
class TaskStatus(str, Enum):
    RECEIVED = "received"
    POLICY_BLOCKED = "policy_blocked"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### RunnerCapabilities

```python
@dataclass
class RunnerCapabilities:
    name: str
    supports_read_mode: bool
    supports_write_mode: bool
    supports_streaming: bool
    supports_resume: bool
    supports_json_output: bool
    supports_permission_mode: bool
    supports_native_hooks: bool
    supports_mcp: bool
    supports_http_runtime: bool
```

### CodingAgentRunner

```python
class CodingAgentRunner(Protocol):
    name: str
    capabilities: RunnerCapabilities

    def prepare(self, task: GatewayTask, workspace: Path) -> None:
        ...

    def run(
        self,
        task: GatewayTask,
        workspace: Path,
        artifacts: ArtifactPaths,
    ) -> RunnerResult:
        ...

    def cancel(self, task_id: str) -> CancelResult:
        ...

    def normalize_result(self, raw: RunnerRawResult) -> RunnerResult:
        ...
```

### RunnerResult

```python
@dataclass
class RunnerResult:
    success: bool
    exit_code: int
    summary: str
    stdout_path: str
    stderr_path: str
    session_id: str | None
    changed_files: list[str]
    token_usage: dict[str, Any] | None
    cost: dict[str, Any] | None
    metadata: dict[str, Any]
```

### ChannelCommand

```python
@dataclass
class ChannelCommand:
    channel: str
    actor: ActorRef
    conversation_id: str | None
    message_id: str | None
    command: str
    args: dict[str, str]
    body: str
    raw_event: dict[str, Any]
```

### NotificationPort

```python
class NotificationPort(Protocol):
    def send(self, task: GatewayTask, message: NotificationMessage) -> NotificationResult:
        ...

    def update(self, task: GatewayTask, message: NotificationMessage) -> NotificationResult:
        ...
```

## Command Contract

Canonical user command:

```text
/agent runner=<runner> repo=<repo> mode=<read|write> workspace=<workspace> [allow=...] [verify=...]
<prompt>
```

`runner` is required on public command and tool task creation surfaces. The
first supported runner is `codex`, but it must be selected explicitly; there is
no implicit Codex default in the public contract.

Examples:

```text
/agent runner=codex repo=example-repo mode=read workspace=inspect-001
Summarize the runtime architecture. Do not modify files.
```

Approval and status:

```text
/agent approve queued_xxx
/agent reject queued_xxx
/agent status queued_xxx
/agent cancel queued_xxx
```

## A2A Positioning

A2A should be implemented as an adapter after the gateway core and command/task
contracts stabilize.

Current next A2A-facing target:

- define the internal gateway descriptor a future AgentCard generator would
  consume;
- define A2A-message-to-gateway-task intake mapping;
- define gateway task status, artifact, approval, and audit views for a future
  adapter;
- connect those internal views to real queue records, `task.json`, and
  allowlisted artifact previews;
- keep all transport bindings, routes, SDK dependencies, and compatibility
  claims out of this phase.

Later endpoint implementation candidates, after the internal contract is tested
and a binding/version/auth plan is approved:

- `GET /.well-known/agent-card.json`
- `POST /message:send`
- `GET /tasks/{task_id}`
- `GET /tasks`
- Artifact listing

Deferred:

- Streaming.
- Subscribe.
- Signed agent card.
- Extended auth.

Do not describe the project as protocol-compatible until the adapter is
implemented and verified.

## Security Model

Read mode:

- No file modifications allowed.
- Runner maps to its safest read/plan mode when available.
- Any workspace changes detected after execution fail the task.

Write mode:

- Requires approval.
- Uses isolated worktree when possible.
- Uses path denylist and changed-path allowlist.
- Runs verify commands before reporting success.
- Captures artifacts and audit data.

Success condition:

```text
runner_success
AND path_guard_passed
AND verify_passed
AND artifact_capture_completed
```

Forbidden by default:

- Runner bypass / yolo / unrestricted modes.
- Sensitive paths such as `.env`, keys, secrets, credentials, auth files,
  `.git`, `.hermes`, `.codex`, `.claude`.
- Unbounded output.
- Untracked network policy assumptions.

## Phased Roadmap

### Phase 0: Rebaseline Current Assets

Goal:

- Record current behavior and identify reusable assets.
- Freeze the intended new public contract before code changes.
- No compatibility promise for old names.

Deliverables:

- This architecture plan.
- `docs/RUNNER_CONTRACT.md`.
- `docs/CHANNEL_CONTRACT.md`.
- `docs/SECURITY_MODEL.md`.
- Baseline tests for queue, worktree, approval, verify, artifacts.

### Phase 1: Hard-Cut Public Identity

Goal:

- Rename public project identity to Hermes Agent Gateway.
- Replace public Codex-specific command/tool/schema names with agent-generic names.

Touchpoints:

- `plugin.yaml`
- `pyproject.toml`
- root `__init__.py`
- package directory rename to `hermes_agent_gateway`
- `config.example.json`
- `README.md`
- `docs/*`
- `skills/*`
- tests

Acceptance:

- `/agent` is accepted.
- `/codex` is rejected.
- No public tool name contains `codex`.
- No public callback key contains `codex`.
- The implementation package directory is renamed to `hermes_agent_gateway`.
- If root `__init__.py` is retained for Hermes plugin loading, it is only a
  thin shim importing from `hermes_agent_gateway`; it must not reintroduce old
  public tool names.

### Phase 2: Channel Boundary

Goal:

- Move Feishu/Lark-specific parsing and notification into channel adapter code.
- Core task and approval models use `ActorRef`, `SourceRef`, and neutral
  notification fields.

Acceptance:

- Gateway Core tests do not construct Feishu raw events.
- Feishu adapter maps platform fields into neutral core fields.

### Phase 3: Runner Boundary

Goal:

- Extract the current subprocess runner into a runner implementation behind
  `CodingAgentRunner`.
- Keep Gateway Core independent of runner-specific flags and session fields.

Acceptance:

- Core task service can run with a fake runner.
- Runner capability mapping is tested.
- Runner-specific terms remain in runner implementation modules only.

### Phase 4: Minimum A2A Adapter

Goal:

- Add A2A-facing internal contract mapping after the core model stabilizes.
- Define descriptor, message intake, task view, artifact view, approval/risk
  view, and audit view before transport work.
- Connect internal views to real `FileTaskQueue` records and gateway-owned
  artifact files with fixed-basename reads, containment checks, preview limits,
  and recursive sanitization.

Acceptance:

- A2A-facing mapping does not depend on Feishu/Lark internals.
- A2A-facing capabilities derive only from enabled runner registry and gateway
  policy.
- Gateway status, approval, risk, verification, and artifacts have explicit
  internal mapping semantics.
- Queue `task_id` remains task-facing identity; execution ids remain metadata.
- Artifact previews are bounded and cannot escape the resolved artifact
  directory.
- No endpoint, SDK dependency, streaming, subscribe, or compatibility claim yet.

### Phase 5: Additional Runners

Goal:

- Add one runner at a time based on verified CLI/API behavior.

Suggested order:

1. Generic CLI runner.
2. Claude Code runner.
3. DeepSeek-TUI runner.
4. OpenCode runner.
5. Qoder/Trae spike runners.

Acceptance:

- Each runner has `RunnerCapabilities`.
- Each runner has read/write permission mapping.
- Each runner has artifact and path-guard tests.

### Phase 6: A2A Streaming / Subscribe

Goal:

- Add streaming once task and artifact models are stable.

Acceptance:

- Task status streaming.
- Artifact update streaming.
- Cancel/subscribe behavior tested.

## Verification Gates

Public hard-cut gate:

```bash
rg -n "hermes-codex-gateway|Hermes Codex Gateway|hermes_local_agent_gateway|/codex|hermes_codex_action|create_codex_task|submit_codex_command|run_next_codex_task|deliver_codex_task_result|ensure_codex_worker_cron|get_codex_task_status|approve_codex_task|manage_codex_workspace|codex-queue-worker|codex_queue_worker|codex_queue_task_id|codex_queue_worker_wake.py|codex_session_id|requested_codex_session_id|Codex task|Codex approval|Codex write approval|CREATE_CODEX_TASK_SCHEMA|SUBMIT_CODEX_COMMAND_SCHEMA|RUN_NEXT_CODEX_TASK_SCHEMA|DELIVER_CODEX_TASK_RESULT_SCHEMA|ENSURE_CODEX_WORKER_CRON_SCHEMA|CODEX_TASK_STATUS_SCHEMA|APPROVE_CODEX_TASK_SCHEMA|MANAGE_CODEX_WORKSPACE_SCHEMA|parse_codex_command|CodexCommand" \
  plugin.yaml pyproject.toml README.md OPERATIONS.md SECURITY.md __init__.py skills tests hermes_agent_gateway docs \
  --glob '!hermes_agent_gateway/runners/codex.py' \
  --glob '!tests/test_runner.py' \
  --glob '!docs/HERMES_*ARCHITECTURE_PLAN.md' \
  --glob '!docs/upstream-pr-plan.md'
```

Expected:

- No hits in public runtime surfaces, public docs, public tests, tool schemas,
  command parser, channel adapter labels, or Gateway Core after Phase 1.
- Runner-private implementation, runner-private tests, and reference/planning
  docs are excluded from this grep.
- Planning artifacts under `.omx/plans/*`, `docs/HERMES_*ARCHITECTURE_PLAN.md`,
  and `docs/upstream-pr-plan.md` are planning/reference artifacts, not runtime
  public surfaces.
- Negative tests should construct old forbidden strings from fragments rather
  than writing exact forbidden literals into test source.

Codex runner allowlist review:

```bash
rg -n "Codex|codex" hermes_agent_gateway tests docs README.md OPERATIONS.md SECURITY.md __init__.py plugin.yaml pyproject.toml skills
```

Expected:

- Allowed hits are limited to runner-private implementation, runner-private
  tests, explicit runner catalog/contract wording, and examples such as
  `runner=codex`.
- No hit may present Codex as the product identity, public package identity,
  public tool identity, callback identity, queue worker identity, or public
  session field identity.
- Planning/reference docs may contain old names only as historical rationale,
  not as current public instructions.

Positive contract gate:

```bash
rg -n "Hermes Agent Gateway|hermes-agent-gateway|hermes_agent_gateway|/agent|hermes_agent_action|create_agent_task|submit_agent_command|run_next_agent_task|deliver_agent_task_result|ensure_agent_worker_cron|get_agent_task_status|approve_agent_task|manage_agent_workspace|agent-queue-worker|agent_session_id" \
  plugin.yaml pyproject.toml README.md OPERATIONS.md SECURITY.md docs __init__.py skills tests
```

Regression:

```bash
PYTHONPATH=. python -m pytest tests -q
python -m compileall -q hermes_agent_gateway
scripts/sanitize-check.sh
```

Targeted suites:

```bash
PYTHONPATH=. python -m pytest \
  tests/test_command_parser.py \
  tests/test_feishu_route.py \
  tests/test_task_service.py \
  tests/test_runner.py \
  tests/test_scheduler_integration.py \
  -q
```

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Overbuilding A2A too early | Keep A2A minimum adapter after core stabilization; defer streaming. |
| Feishu leaks into core | Add channel-neutral model tests and grep gates for platform fields in core. |
| Runner-specific assumptions leak into core | Use `RunnerCapabilities` and fake-runner tests. |
| Hard cut misses an old public symbol | Use explicit old-token grep gate before merge. |
| Security regression during runner expansion | Add runner permission matrix and deny bypass/yolo modes by default. |
| Naming churn | Freeze product name as Hermes Agent Gateway for this planning baseline. |

## First Implementation Slice

The first implementation slice should not add Claude Code, DeepSeek-TUI, Qoder,
Trae, or A2A HTTP endpoints.

It should do only:

1. Rename public identity to Hermes Agent Gateway.
2. Replace public command/tool/schema names with agent-generic names.
3. Introduce channel and runner contract documents.
4. Introduce neutral domain model stubs if needed.
5. Keep existing governance behavior working through the renamed public surface.
6. Add negative tests that old `/codex` and old tool names are not registered.

This gives the project the correct long-term shape before expanding the runner
and protocol matrix.
