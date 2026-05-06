# RALPLAN-DR: A2A Real Task And Artifact Views

Task:
- Plan the next larger execution batch for the A2A-facing internal contract.
- Connect the mapping-only contract to real Gateway Core queue records, task-service task records, and Gateway-owned artifact files.
- Keep the work internal and read-only: no endpoint, route, SDK, transport binding, streaming, subscribe, push notification, auth binding, AgentCard serving, runner/channel addition, or compatibility claim.

Evidence:
- Current planning HEAD `255272a` follows implementation commit `8a54526`, which added `hermes_agent_gateway/a2a_gateway_contract.py`, `tests/test_a2a_gateway_contract.py`, and `tests/test_a2a_gateway_contract_static.py`.
- `a2a_gateway_contract.py` currently maps in-memory mappings to descriptor, message, task state, artifact, and event views, and sanitizes paths.
- `queue.py` persists `FileTaskQueue` records with `queued_*` task ids, status, payload, optional result, approval, delivery result, approval card data, and card updates.
- `task_service.py` creates separate `agent_*` execution task ids and writes `task.json` plus `agent_stdout.jsonl`, `agent_stderr.log`, before/after git status/diff/stat, `verify_results.json`, and verify stdout/stderr files.
- `artifacts.py` owns task id generation, artifact directory creation, git capture, and JSON writing.
- Static tests currently block endpoint/transport tokens, public compatibility claims, and private runner/channel field leakage.

## Principles

1. Preserve Gateway Core ownership: approval, risk, path guard, verification, artifact persistence, audit, and queue lifecycle remain Gateway Core concerns.
2. Project, do not bind: produce internal read-only views that a future adapter can consume, without selecting or implying an A2A transport/schema binding.
3. Keep identities explicit: queue `queued_*` ids are task-facing ids; task-service `agent_*` ids are execution/artifact run metadata.
4. Read only Gateway-owned artifacts: artifact views must be allowlisted, bounded, sanitized, and contained under the resolved artifact directory.
5. Fail closed on claims: docs and static gates must continue rejecting endpoints, public compatibility wording, private channel fields, and unimplemented capabilities.

## Decision Drivers

1. The next batch should be coherent enough for Ralph/team execution, not another tiny mapping-only helper slice.
2. The implementation must not accidentally create a protocol-shaped file browser, endpoint surface, or compatibility claim.
3. The plan must leave later endpoint work free to choose actual A2A enum spelling, error representation, auth model, and conformance path.

## Viable Options

### Option A: Keep Projection Helpers In `a2a_gateway_contract.py`

Pros:
- Tightest scope and easiest static gate coverage.
- Keeps A2A-facing vocabulary in one internal module.
- Avoids creating a general artifact-reading API.

Cons:
- The module grows beyond pure mapping into bounded file projection.
- Some safe-read code may become reusable later and need extraction.

### Option B: Add A Generic Gateway Artifact Reader In `artifacts.py`

Pros:
- Reusable by delivery, docs, or future adapters.
- Keeps file IO near artifact ownership.

Cons:
- Higher risk of becoming a broad file access surface.
- Requires careful naming to avoid A2A-specific concepts in generic artifact code.

### Option C: Read Only Queue `result` And `task.json` Metadata

Pros:
- Safest and smallest.
- Avoids file preview and containment complexity.

Cons:
- Does not satisfy the requested artifact reading views.
- Leaves stdout/stderr/diff/verify logs disconnected from the internal contract.

Recommended:
- Choose Option A for this batch, with one escape hatch: add only a tiny generic bounded-read helper to `artifacts.py` if implementation becomes awkward, and keep it Gateway-named, allowlist-oriented, and free of A2A terms.

Rejected:
- Do not use execution `agent_*` ids as task-facing ids; that confuses queue approval/status lookup with execution artifacts.
- Do not reuse delivery extraction as the source of truth; delivery currently formats channel-facing summaries and may expose artifact paths where A2A-facing projection must sanitize and bound content.
- Do not add endpoint/schema/SDK stubs or placeholder protocol fields.

## Recommended Scope

Add a read-only internal projection layer over existing persistence.

Primary work:
- Add task record projection helpers that accept queue records and produce a richer internal task view with:
  - `task_id` from the queue record (`queued_*`);
  - optional `execution_task_id` from queue `result.task_id` or artifact `task.json.task_id` (`agent_*`);
  - semantic lifecycle from queue `status`;
  - terminal flag and future-binding markers from current `gateway_task_state_view`;
  - sanitized payload/result/approval/risk/verification/audit summaries;
  - no delivery channel private fields.
- Add artifact projection helpers that read only Gateway-owned files under the resolved artifact directory:
  - `task.json`;
  - `agent_stdout.jsonl`;
  - `agent_stderr.log`;
  - `before_status.txt`, `after_status.txt`;
  - `before_diff.txt`, `after_diff.txt`;
  - `before_diff_stat.txt`, `after_diff_stat.txt`;
  - `verify_results.json`;
  - `verify_N_stdout.log` and `verify_N_stderr.log` only after raw
    `verify_results.json` entries are mapped to fixed verify log basenames,
    containment-checked under the artifact directory, and then sanitized for
    returned metadata/text.
- Add bounded preview metadata for text artifacts:
  - default preview limit: 16 KiB per stdout/stderr/verify log;
  - default preview limit: 64 KiB per diff;
  - default preview limit: 8 KiB for prompt/error text in summaries;
  - include `truncated`, `bytes_read`, and `limit_bytes` metadata.
- Missing/corrupt artifact files should produce non-throwing omission or error metadata by default; strict mode can raise if useful, but default contract projection should be resilient.
- Strengthen docs and static gates to state this is internal projection only.

Status precedence:
- Queue record `status` is authoritative for task lifecycle.
- Queue `result.success`, queue `result.status`, and artifact `task.json.status` may refine reason, execution summary, and audit metadata only.
- Mismatches must not override queue lifecycle state in the A2A-facing internal task view.

Containment rule:
- Resolve the artifact directory and only read fixed allowlisted basenames beneath it.
- Omit or reject traversal attempts, symlink escapes, unknown files, and verify log paths that do not resolve under the artifact directory.
- Sanitization is required after reading, but sanitization is not a substitute for containment.

## Deliverables

1. PRD: `.omx/plans/prd-a2a-real-task-artifact-views-20260506.md`.
2. Test spec: `.omx/plans/test-spec-a2a-real-task-artifact-views-20260506.md`.
3. Code changes likely in:
   - `hermes_agent_gateway/a2a_gateway_contract.py`;
   - optionally `hermes_agent_gateway/artifacts.py` for a generic bounded read helper only.
4. Tests likely in:
   - `tests/test_a2a_gateway_contract.py`;
   - `tests/test_a2a_gateway_contract_static.py`;
   - focused fixture reuse from `tests/test_task_service.py` or new fixture helpers if needed.
5. Docs likely in:
   - `docs/A2A_FACING_GATEWAY_CONTRACT_PLAN.md`;
   - `docs/HERMES_AGENT_GATEWAY_ARCHITECTURE_PLAN.md`.

## Acceptance Criteria

- Queue/task identity:
  - A real `FileTaskQueue` record projects `queued_*` as the internal task-facing id.
  - A task-service `agent_*` id appears only as execution/artifact metadata.
- Lifecycle:
  - Tests cover `QUEUED`, `RUNNING`, `APPROVAL_REQUIRED`, `REJECTED`, queue `FAILED`, queue `DONE`, and blocked execution results.
  - Mismatch tests prove queue `FAILED` with artifact `DONE`, and queue `DONE` with failed execution metadata, do not let artifact metadata silently replace queue lifecycle.
- Artifact projection:
  - Reads are limited to the allowlisted Gateway-owned basenames.
  - `verify_N_stdout.log` and `verify_N_stderr.log` are read only when referenced by `verify_results`.
  - Missing and corrupt artifact files do not crash default projection.
  - Traversal, symlink escape, and unknown-file attempts are omitted or rejected.
- Bounding/sanitization:
  - Large stdout/stderr/verify logs truncate at 16 KiB.
  - Large diffs truncate at 64 KiB.
  - Prompt/error previews truncate at 8 KiB.
  - Returned payloads include truncation metadata and redact absolute/private paths.
- Static/docs gates:
  - No endpoint, route, transport, SDK, stream, subscribe, push notification, auth binding, AgentCard serving, new runner/channel, or compatibility claim tokens are added.
  - Public docs say internal A2A-facing contract/projection only and explicitly avoid compatibility language.
- Regression:
  - Existing queue, task service, delivery, and contract behavior remains unchanged.

## Risks

- Identity confusion between `queued_*` queue tasks and `agent_*` execution artifacts.
- Artifact projection becoming a general file browser if containment and allowlists are weak.
- Static gates becoming too broad and blocking deferred planning docs.
- Overfitting to current artifact filenames without clear default behavior for missing future files.

## Verification

Run after implementation:
- `uv run pytest tests/test_a2a_gateway_contract.py tests/test_a2a_gateway_contract_static.py`
- `uv run pytest tests/test_queue.py tests/test_task_service.py tests/test_scheduler_integration.py`
- `uv run pytest`
- `rg -n "message:send|message/send|message:stream|message/stream|text/event-stream|pushNotificationConfig|agent/getAuthenticatedExtendedCard|A2A-compatible|a2a-compatible|supports A2A|full A2A|A2A server|serves A2A|exposes A2A|implements A2A|A2A support" hermes_agent_gateway tests docs`

The final report should include changed files, projection boundaries, static-gate evidence, test evidence, and any remaining deferred endpoint/binding decisions.

## Execution Lanes

### Ralph Sequential Lane

Recommended for a single-owner coherent batch.

1. Draft PRD and test spec artifacts under `.omx/plans/`.
2. Extend `a2a_gateway_contract.py` with task projection and artifact projection helpers.
3. Add fixture-backed unit tests for queue/task identity, lifecycle precedence, artifact reading, containment, truncation, and sanitization.
4. Update docs and static gates.
5. Run targeted tests, then full tests, then static grep.
6. Commit with Lore protocol.

Suggested role/reasoning:
- `executor`, medium reasoning for implementation.
- `verifier`, high reasoning for final evidence if using native subagents.

### Team Lane

Use only if parallel execution is desired.

Available agent types:
- `executor`, `test-engineer`, `writer`, `verifier`, `code-reviewer`, `architect`, `critic`, `explore`.

Staffing:
- Lane 1, `executor`: implementation in `a2a_gateway_contract.py` and optional generic helper in `artifacts.py`.
- Lane 2, `test-engineer`: tests in `tests/test_a2a_gateway_contract.py` and static gate updates.
- Lane 3, `writer`: docs plus PRD/test spec artifacts.
- Lane 4, `verifier`: run targeted/full tests and static grep after integration.

Reasoning:
- Implementation: medium.
- Tests: medium.
- Docs: low or medium.
- Verification/code review: high.

Launch hint:
- `$team "Execute .omx/plans/ralplan-a2a-real-task-artifact-views-20260506.md with disjoint lanes for implementation, tests, docs, and verification. Preserve all hard non-goals."`

Team verification path:
- Verifier runs targeted contract/static tests first, then task/queue/scheduler regression tests, then full pytest, then static grep.
- Code reviewer checks identity/status precedence, containment, truncation metadata, and docs claim posture before final handoff.

## ADR

Decision:
- Implement an internal read-only projection layer over real Gateway queue records and artifact files, keeping the queue id as the task-facing identity and execution ids as metadata.

Drivers:
- Larger coherent batch requested.
- Existing persistence already records queue lifecycle and artifacts.
- Endpoint/binding/compatibility work remains explicitly deferred.

Alternatives considered:
- Generic artifact reader in `artifacts.py`: deferred unless needed for a tiny bounded helper.
- Metadata-only projection: rejected because it does not connect real artifact views.
- Execution-id-facing task identity: rejected because approval/status ownership lives in the queue.

Why chosen:
- It advances the A2A-facing internal contract while preserving Gateway Core boundaries and future protocol-binding freedom.

Consequences:
- `a2a_gateway_contract.py` becomes the main internal projection surface.
- Tests must now cover filesystem containment and truncation, not just mapping.
- Later endpoint work can consume stable internal projections without inheriting filesystem or queue internals.

Follow-ups:
- Later plan must choose actual A2A binding, task enum spelling, auth model, AgentCard exposure rules, streaming/subscription posture, and conformance tests.
