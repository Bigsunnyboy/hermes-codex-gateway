# Test Spec: A2A Real Task And Artifact Views

Date: 2026-05-06
Status: consensus draft
Scope: future Ralph implementation of internal real-record/artifact views

## Focused Unit Tests

### Queue record view

Cases:
- queued record maps to submitted semantic state;
- running record maps to working semantic state;
- approval-required record keeps approval-needed future-binding flag;
- rejected record keeps rejected future-binding flag;
- blocked record keeps risk reason and rejected-or-failed candidate states;
- completed record with result maps to completed and includes sanitized result;
- failed record maps to failed and includes bounded error reason;
- unknown status raises a closed failure.

Assertions:
- queue ids and timestamps are preserved;
- payload/result values are recursively sanitized;
- raw platform delivery fields are not exposed as public A2A-facing field names;
- missing optional record fields do not crash view construction.
- queue `task_id` remains task-facing identity when `result.task_id` or
  `task.json.task_id` contains a different `agent_*` execution id;
- queue `status` remains authoritative when `result.status` or
  `task.json.status` disagrees.

### Task JSON reader

Cases:
- valid `task.json` is parsed and sanitized;
- missing `task.json` is omitted or represented as a missing optional artifact;
- invalid `task.json` produces bounded error metadata;
- absolute paths in string values and nested arrays/maps are redacted.

### Artifact manifest reader

Cases:
- stdout/stderr/status/diff/verify files are included when present;
- missing optional files are omitted;
- diff files are bounded more tightly than stdout/stderr;
- verify results JSON is parsed and sanitized;
- invalid verify JSON becomes bounded error metadata;
- large stdout/stderr files are truncated with `truncated=true`;
- artifact reader refuses to traverse outside the provided artifact directory.
- reads are limited to fixed Gateway-owned basenames under the resolved artifact
  directory;
- symlink escapes are omitted or rejected;
- unknown files are ignored;
- stdout/stderr/verify logs are bounded to 16 KiB and expose `truncated`,
  `bytes_read`, and `limit_bytes`;
- diff/diff-stat previews are bounded to 64 KiB and expose `truncated`,
  `bytes_read`, and `limit_bytes`;
- prompt/error summaries are bounded to 8 KiB and expose equivalent preview
  metadata;
- verify stdout/stderr logs are read only after raw `verify_results.json`
  entries are parsed, mapped to fixed `verify_N_stdout.log` /
  `verify_N_stderr.log` basenames, and containment-checked under the artifact
  directory; returned metadata is sanitized after the read target is resolved;
- absolute external paths in verify result stdout/stderr path fields are
  redacted and never used as read targets.

### Combined task view

Cases:
- queue record with `result.artifact_dir` produces state + sanitized result +
  artifact manifest;
- queue record without artifacts still returns a state and sanitized record view;
- approval-required record does not attempt artifact reads unless artifact_dir is
  present;
- blocked record carries risk metadata without endpoint-specific error shape.
- queue `FAILED` with artifact `task.json.status=DONE` remains failed;
- queue `DONE` with artifact `task.json.status=FAILED` remains completed but
  includes mismatch/audit metadata.

### Static gates

Cases:
- implementation files contain no endpoint tokens, route decorators, HTTP
  framework imports, streaming tokens, or protocol transport names;
- public docs contain no compatibility claims;
- dependency files do not change for A2A/HTTP/streaming dependencies;
- reserved runners are not advertised as enabled;
- A2A-facing output field names avoid runner-private and raw Feishu/Lark names.

## Suggested Commands

Focused tests:

```bash
PYTHONPATH=. pytest tests/test_a2a_gateway_contract.py tests/test_a2a_gateway_contract_static.py -q
```

Full regression:

```bash
PYTHONPATH=. pytest tests -q
python3 -m compileall -q hermes_agent_gateway tests
scripts/sanitize-check.sh
git diff --check
```

Static endpoint gate:

```bash
rg -n "message:send|message/send|message:stream|message/stream|tasks/get|tasks/cancel|tasks/resubscribe|/v1/message:send|/v1/tasks|pushNotificationConfig|agent/getAuthenticatedExtendedCard|text/event-stream|FastAPI|Flask|APIRouter|route\\(" hermes_agent_gateway
```

Expected: no matches.

Compatibility claim gate:

```bash
rg -n "A2A-compatible|a2a-compatible|supports A2A|full A2A|A2A server|serves A2A|exposes A2A|implements A2A|A2A support" README.md OPERATIONS.md docs skills __init__.py hermes_agent_gateway tests
```

Expected: no matches except test strings that are constructed to avoid literal
claim text.

Private leakage gate:

```bash
rg -n "CodexCliRunner|codex_executable|feishu_router|event\\.message_id|event\\.source|chat_id|approval_card" hermes_agent_gateway/a2a_gateway_contract.py tests/test_a2a_gateway_contract.py tests/test_a2a_gateway_contract_static.py docs/A2A_FACING_GATEWAY_CONTRACT_PLAN.md docs/A2A_REAL_TASK_ARTIFACT_VIEWS_PLAN.md
```

Expected: no matches except explicit rejected/deferred docs if tests scope them
out.

## Review Gates

- Architect approves that internal views do not mutate Gateway Core behavior.
- Architect approves artifact sanitization and preview bounds.
- Critic/verifier confirms acceptance criteria are testable and large enough for
  one meaningful Ralph batch.
- Deslop pass stays scoped to changed files.
- Post-deslop regression stays green.

## Out Of Scope

- A2A endpoint conformance.
- HTTP+JSON binding.
- Auth/security scheme presentation.
- Streaming, subscribe, push notification, cancel, task listing.
- Queue storage migration.
- Runner/channel additions.
