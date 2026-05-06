# A2A Real Task And Artifact Views Context

Task statement:
- Plan a larger next execution batch for the A2A-facing Gateway Contract.
- Connect the current mapping-only contract to real Gateway Core task records
  and artifact file reading views.
- Add docs/static gates.
- Still do not implement endpoint, route, SDK, protocol binding, streaming, or
  compatibility claims.

Desired outcome:
- A larger, execution-ready plan that Ralph can implement in one coherent pass.
- The next implementation should expose internal, sanitized views over:
  - queue records from `FileTaskQueue`;
  - completed task payloads from `task.json`;
  - gateway-owned artifact files such as stdout, stderr, git status/diff, and
    verification outputs.
- Public docs should be explicit that this is internal contract plumbing only.

Known facts and evidence:
- `hermes_agent_gateway/a2a_gateway_contract.py` currently defines internal
  descriptor, message envelope, task state, artifact, and event semantic views.
- That module currently operates on in-memory mappings supplied by the caller;
  it does not load a queue record or read artifact files.
- `hermes_agent_gateway/queue.py` persists queue records with `task_id`,
  `status`, `payload`, optional `result`, optional `approval`, delivery state,
  and card update records.
- `hermes_agent_gateway/task_service.py` writes `task.json` into the task
  artifact directory and records fields such as task id, mode, runner, paths,
  command, return code, verify results, risk, workspace change, and error.
- `hermes_agent_gateway/artifacts.py` writes gateway-owned artifact files:
  `task.json`, `agent_stdout.jsonl`, `agent_stderr.log`, `before_status.txt`,
  `after_status.txt`, `before_diff*.txt`, `after_diff*.txt`, and verification
  result files.
- Official A2A specification currently separates data objects/events from
  HTTP+JSON endpoint binding. The endpoint binding remains out of scope.

Constraints:
- Plan only in this ralplan turn.
- Next Ralph batch should be larger than the previous mapping-only helper slice.
- No A2A endpoint, route registration, SDK dependency, streaming, subscribe,
  push notification, auth binding, AgentCard serving, or compatibility claim.
- Do not expose raw absolute paths, runner command paths, sensitive files, or
  raw Feishu/Lark event fields in A2A-facing views.
- Keep Gateway Core ownership of approval, risk, path guard, verification,
  artifact persistence, and audit.
- Preserve current queue/task behavior; this batch should read and normalize
  existing records, not migrate storage.
- Leave unrelated `.gitignore` modifications untouched.

Unknowns/open questions:
- Whether later endpoint work will choose HTTP+JSON, JSON-RPC, gRPC, or another
  binding.
- Exact A2A enum/error mapping remains deferred.
- How much stdout/stderr/diff text should be exposed by default versus only
  summarized; the plan should define bounded previews and metadata.

Likely codebase touchpoints:
- `hermes_agent_gateway/a2a_gateway_contract.py`
- possible new internal helper module only if it reduces coupling;
- `hermes_agent_gateway/artifacts.py` if reusable safe-read helpers belong
  there;
- `tests/test_a2a_gateway_contract.py`
- `tests/test_a2a_gateway_contract_static.py`
- `tests/test_task_service.py` or focused fixture tests for real task records;
- `docs/A2A_FACING_GATEWAY_CONTRACT_PLAN.md`
- `docs/HERMES_AGENT_GATEWAY_ARCHITECTURE_PLAN.md`
- `.omx/plans/prd-a2a-real-task-artifact-views-20260506.md`
- `.omx/plans/test-spec-a2a-real-task-artifact-views-20260506.md`
