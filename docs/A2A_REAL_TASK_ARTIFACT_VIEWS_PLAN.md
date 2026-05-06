# A2A Real Task And Artifact Views Plan

This plan is the next larger execution batch after the mapping-only
A2A-facing contract. It connects that contract to real Gateway Core task
records and gateway-owned artifact files without adding any A2A endpoint,
route, SDK, transport binding, streaming behavior, or compatibility claim.

## Decision

Extend the internal A2A-facing contract so it can build sanitized views from:

- `FileTaskQueue` records;
- `task.json` payloads written by `create_agent_task`;
- gateway-owned artifact files under each task artifact directory.

The implementation should remain an internal read/normalization layer. It must
not serve protocol objects over the network, register routes, or change queue,
task execution, approval, verification, delivery, runner, or channel behavior.

## Batch Scope

### 1. Real Task Record View

Add internal functions that accept a real queue record and return one composed
task view:

- queue identity: `task_id`, queue status, created/updated timestamps;
- sanitized payload fields: runner, mode, repo/path/workspace/session, prompt
  presence/preview, verify commands, allowed paths, risk, approval;
- sanitized result fields when present;
- existing semantic task state from the A2A-facing contract;
- approval/risk metadata without Feishu/Lark raw event fields.

The function may accept a plain mapping so tests can use fixture records, but it
should be shaped around the current `FileTaskQueue` record schema.

### 2. Artifact File Manifest

Add an internal artifact reader that takes an artifact directory and produces a
bounded, sanitized manifest:

- `task_record`: parsed and sanitized `task.json`;
- `stdout`: bounded preview from `agent_stdout.jsonl`;
- `stderr`: bounded preview from `agent_stderr.log`;
- `before_status` / `after_status`;
- `before_diff_stat` / `after_diff_stat`;
- `before_diff` / `after_diff` with tighter preview limits;
- `verification`: parsed `verify_results.json` plus optional bounded verify
  stdout/stderr references;
- `audit`: derived from task record risk, runner, mode, return code, workspace
  changed, approval, and timestamps when available.

Missing optional files should be omitted. Invalid JSON should fail closed for
that artifact item with a bounded error metadata item, not crash the entire
task view.

Artifact reads must be allowlisted and contained:

- resolve the artifact directory before reading;
- read only known Gateway-owned basenames beneath that directory;
- omit or reject unknown files, traversal attempts, and symlink escapes;
- parse raw `verify_results.json`, map entries only to fixed
  `verify_N_stdout.log` / `verify_N_stderr.log` basenames, containment-check
  those targets under the resolved artifact directory, then sanitize returned
  metadata/text.

Preview limits:

- stdout, stderr, and verify logs: 16 KiB each;
- diffs and diff stats: 64 KiB each;
- prompt/error summary text: 8 KiB each.

Every preview item should include `truncated`, `bytes_read`, and `limit_bytes`.

### 3. Combined Gateway Task View

Add a single internal builder that combines:

- a queue record;
- optional result `artifact_dir`;
- optional artifact directory reader output;
- semantic task state;
- sanitized task/result/artifact categories.

This builder is the main output for future A2A adapter work. It is still not a
protocol response and must not use protocol route or endpoint names.

Identity and lifecycle precedence:

- queue record `task_id` (`queued_*`) is the task-facing identity;
- execution `agent_*` ids from task results or `task.json` are metadata only;
- queue `status` is authoritative for lifecycle;
- `result.status` and `task.json.status` may refine reason/audit metadata but
  must not override queue lifecycle.

### 4. Docs And Static Gates

Update docs to state that the gateway now has internal real-record/artifact
views, but still does not expose A2A endpoints or compatibility.

Extend static gates so future changes fail if the internal contract module
adds:

- endpoint tokens;
- transport imports or route registration;
- protocol compatibility claims;
- planning-only runner advertisement;
- raw Feishu/Lark event fields or runner-private execution fields in public
  A2A-facing output names.

## Non-Goals

- No A2A HTTP+JSON endpoint.
- No `AgentCard` serving, extended card, or signed card.
- No `message/send`, streaming, subscribe, cancel, task listing, push
  notification, auth binding, or protocol conformance behavior.
- No A2A SDK or HTTP framework dependency.
- No queue storage migration.
- No change to scheduler execution behavior.
- No change to approval, risk, path guard, verification, artifact capture, or
  delivery behavior.
- No new runner or channel.
- No public compatibility claim.

## Implementation Notes For Ralph

Recommended file ownership:

- `hermes_agent_gateway/a2a_gateway_contract.py`: extend the current internal
  contract with record/artifact builders and bounded read helpers.
- `tests/test_a2a_gateway_contract.py`: add fixture tests for queue/result
  records, artifact directory manifests, missing files, invalid JSON, bounded
  previews, recursive path sanitization, and combined views.
- `tests/test_a2a_gateway_contract_static.py`: widen static gates to include
  the new reader surface and dependency/route checks.
- `docs/A2A_FACING_GATEWAY_CONTRACT_PLAN.md`: describe the real-record/artifact
  view layer as internal only.
- `docs/HERMES_AGENT_GATEWAY_ARCHITECTURE_PLAN.md`: update Phase 4 acceptance
  so real task/artifact views are the next implemented internal step.

If the implementation becomes too large for one file, a new internal module may
be added, but it must stay under `hermes_agent_gateway` and must not introduce
transport dependencies.

## Acceptance Criteria

- Real queue records can be converted into sanitized internal task views.
- `task.json` can be read and sanitized into the same view shape.
- Artifact directories can be read into bounded, sanitized manifests.
- Missing optional artifact files are omitted.
- Invalid artifact JSON is represented as bounded error metadata without
  exposing raw absolute paths.
- Artifact preview items include `truncated`, `bytes_read`, and `limit_bytes`.
- Artifact reads are fixed-basename, contained under the resolved artifact dir,
  and reject/omit symlink escapes.
- Verify stdout/stderr logs follow the raw `verify_results.json` parse,
  fixed-basename mapping, containment-check, then sanitize-returned-metadata
  order.
- Queue `task_id` remains task-facing identity and queue `status` remains
  lifecycle-authoritative when artifact metadata disagrees.
- No raw absolute paths, runner command paths, or private filesystem paths
  appear in protocol-facing strings or nested payloads.
- `APPROVAL_REQUIRED`, `REJECTED`, and `BLOCKED` retain future-binding flags.
- Static tests prove no endpoint/transport/compatibility claim was added.
- Full pytest, compileall, sanitize, diff check, and static grep gates pass.

## Deferred Follow-Ups

- Select A2A binding/version/auth/conformance path.
- Decide final wire mapping for approval-required, rejected, and blocked states.
- Decide whether a future endpoint response returns artifact previews or only
  references.
- Design streaming/subscription only after real task/artifact views are stable.
