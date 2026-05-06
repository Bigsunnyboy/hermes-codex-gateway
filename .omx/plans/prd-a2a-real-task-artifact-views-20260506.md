# PRD: A2A Real Task And Artifact Views

Date: 2026-05-06
Status: consensus draft
Scope: larger implementation batch after the mapping-only A2A-facing contract

## Problem

The current A2A-facing contract is useful but still operates mostly on caller
supplied mappings. It proves the semantic vocabulary, but a future adapter
still needs a real Gateway Core view over queue records, `task.json`, and
artifact files.

The next execution batch should close that gap in one coherent pass. It should
be larger than the previous helper slice, but it must still avoid endpoint,
transport, SDK, streaming, or compatibility scope.

## Desired Outcome

Implement an internal real-record view layer for future A2A adapter work:

- compose sanitized internal task views from `FileTaskQueue` record shapes;
- read and sanitize task `task.json`;
- read bounded artifact previews and verification metadata from artifact
  directories;
- expose one combined internal task view that future transport code can consume;
- expand docs/static gates so this remains internal-only.

## Principles

1. Real Gateway evidence before protocol endpoint.
2. Larger coherent batch, not a tiny helper-only slice.
3. Internal read/normalization only; no runtime behavior change.
4. Sanitization and bounded previews before any protocol-facing artifact view.
5. Gateway Core remains owner of approval, risk, verification, artifacts, and
   audit.

## Decision Drivers

1. The current contract needs to consume real records to become useful.
2. Artifact reading is the highest-risk data exposure surface and must be
   designed before endpoints.
3. User feedback requires larger execution batches that move the roadmap more
   visibly while preserving hard boundaries.

## Options

### Option A: Only add docs for real task/artifact views

Pros:
- Lowest risk.
- No code churn.

Cons:
- Does not address the practical gap between current mapping helpers and real
  Gateway data.
- Keeps the next Ralph execution too small.

Verdict: reject for this phase.

### Option B: Add real-record/artifact internal views, docs, and static gates

Pros:
- Meaningfully advances the A2A-facing roadmap without endpoint work.
- Uses real queue/task/artifact data.
- Lets later adapter work consume tested internal views.
- Matches the requested larger batch size.

Cons:
- More code and tests in one Ralph pass.
- Artifact sanitization and preview limits require careful review.

Verdict: choose.

### Option C: Add internal views plus a private HTTP preview endpoint

Pros:
- Gives a fast manual inspection surface.

Cons:
- Violates the no-endpoint boundary and risks accidental protocol claims.

Verdict: reject.

## Functional Requirements

### Task record view

- Accept a `FileTaskQueue` record shape as a mapping.
- Preserve `task_id`, queue status, created/updated timestamps, approved flag,
  approval metadata, delivery/card update metadata only when sanitized.
- Include sanitized payload and result subviews.
- Derive semantic task state using the existing task state mapping.
- Fail closed on missing or unknown status.

### Task artifact reader

- Read `task.json` from an artifact directory when present.
- Read bounded previews of:
  - `agent_stdout.jsonl`;
  - `agent_stderr.log`;
  - `before_status.txt`;
  - `after_status.txt`;
  - `before_diff_stat.txt`;
  - `after_diff_stat.txt`;
  - `before_diff.txt`;
  - `after_diff.txt`;
  - `verify_results.json`;
  - `verify_*_stdout.log`;
  - `verify_*_stderr.log`.
- Omit missing optional files.
- Represent invalid JSON as a bounded error artifact item.
- Sanitize all text and nested values recursively.
- Enforce preview limits, with tighter limits for diff-like artifacts.

Concrete preview limits:

- stdout/stderr/verify logs: 16 KiB each;
- diff and diff-stat files: 64 KiB each;
- prompt/error summary strings: 8 KiB each.

Every preview object must include:

- `truncated`;
- `bytes_read`;
- `limit_bytes`.

Containment and allowlist policy:

- resolve the artifact directory before reading;
- read only fixed Gateway-owned basenames under the artifact directory;
- do not follow symlink escapes outside the artifact directory;
- omit or reject unknown filenames and traversal attempts;
- never read from paths supplied directly by unsanitized task metadata.

Verify-log policy:

- parse raw `verify_results.json` first;
- use raw verify result entries only to identify fixed
  `verify_N_stdout.log` / `verify_N_stderr.log` basenames;
- validate every verify log read target remains under the resolved artifact
  directory before reading;
- sanitize returned verify metadata and text after the read target is resolved;
- redact absolute paths from verify command/output text.

### Combined internal task view

- Combine queue record, result, semantic state, task record, and artifact
  manifest.
- Use stable internal categories, not A2A wire names.
- Include enough metadata for a future adapter to build Task/Artifact-like
  objects after binding/version selection.
- Preserve queue `task_id` (`queued_*`) as the task-facing identity.
- Treat execution `agent_*` ids from queue result or `task.json` as
  execution/artifact metadata only.
- Treat queue `status` as lifecycle-authoritative. `result.status` and
  `task.json.status` may refine reason/audit metadata but must not override the
  queue lifecycle state.

### Docs/static gates

- Update public/reference docs to state internal real-record/artifact views are
  available after implementation, while endpoints remain absent.
- Add tests/static gates that fail on:
  - endpoint tokens or route registration in implementation files;
  - protocol compatibility claims in public docs;
  - new A2A/HTTP/streaming dependencies;
  - reserved runner advertisement;
  - raw Feishu/Lark event fields or runner-private fields in A2A-facing output
    names.

## Non-Goals

- No endpoint, route, server, SDK, HTTP framework, or protocol client.
- No streaming, subscribe, push notification, cancel, task listing, auth
  binding, AgentCard serving, or compatibility claim.
- No queue migration.
- No task execution behavior change.
- No scheduler, delivery, approval callback, risk policy, path guard,
  verification, artifact capture, runner, or channel behavior change.
- No new runner or channel.

## Acceptance Criteria

- Tests cover queue record view construction across current statuses.
- Tests cover real `task.json` loading and sanitization.
- Tests cover artifact previews, missing optional files, invalid JSON, and
  bounded diff previews.
- Tests assert concrete preview metadata: `truncated`, `bytes_read`, and
  `limit_bytes`.
- Tests assert stdout/stderr/verify log previews are limited to 16 KiB, diffs
  to 64 KiB, and prompt/error previews to 8 KiB.
- Tests cover recursive sanitization for embedded absolute paths in artifacts.
- Tests cover fixed-basename allowlisting, traversal rejection, and symlink
  escape omission/rejection.
- Tests cover verify log reads only when referenced by contained
  `verify_results` entries.
- Tests cover queue/artifact mismatch cases where queue `task_id` and queue
  `status` remain authoritative.
- Tests prove no endpoint/transport/SDK/compatibility surface was added.
- Docs identify this as internal contract plumbing only.
- Full verification path passes:
  - focused A2A contract tests;
  - full pytest;
  - compileall;
  - sanitize;
  - diff check;
  - static grep gates.

## ADR

Decision:
- Execute Option B: a larger internal real task/artifact view batch.

Drivers:
- The A2A-facing contract needs real Gateway Core data to be useful.
- Artifact exposure risk should be handled before endpoint design.
- Larger coherent execution better matches the project velocity expectation.

Alternatives considered:
- Docs-only: too little practical progress.
- Private preview endpoint: too early and violates boundary.

Consequences:
- Later endpoint planning can start from tested internal views.
- Artifact preview policy becomes part of the internal contract.
- Endpoint binding/version/auth/conformance remain deferred.

Follow-ups:
- `$ralph` should implement this entire batch, not split into helper-only
  fragments.
- After this batch, plan endpoint binding/version/auth separately.

## Execution Guidance

Ralph path:
- Implementation lane: extend internal contract with task/artifact readers and
  combined view builder.
- Evidence/regression lane: add artifact fixture tests and static gate tests.
- Sign-off lane: architect reviews data exposure, no-endpoint posture, and
  boundary ownership.

Team path:
- Lane 1, `executor`: implement record/artifact builders.
- Lane 2, `test-engineer`: build fixture tests and static gates.
- Lane 3, `writer`: update docs posture.
- Lane 4, `architect`/`verifier`: review data exposure and no-endpoint gates.

Suggested launch:

```text
$ralph Implement .omx/plans/prd-a2a-real-task-artifact-views-20260506.md using .omx/plans/test-spec-a2a-real-task-artifact-views-20260506.md. Execute the whole real task/artifact view batch. Do not add endpoints, SDKs, streaming, new runners/channels, or compatibility claims.
```
