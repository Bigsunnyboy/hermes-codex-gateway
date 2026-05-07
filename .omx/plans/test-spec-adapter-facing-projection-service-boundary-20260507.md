# Test Spec: Adapter-Facing Projection Service Boundary

## Targeted Unit Tests

Add `tests/test_adapter_projection_service.py`.

Required coverage:
- `AdapterProjectionService.gateway_descriptor()` returns the same enabled runner, runner capability, skill, protocol posture, and governance values currently asserted for `build_gateway_agent_descriptor`.
- `AdapterProjectionService.normalize_message_envelope(payload)` validates enabled runners, mode, actor source, list fields, and preserves the same normalized envelope fields.
- `AdapterProjectionService.message_payload(envelope)` returns the same queue payload shape as the current helper.
- `AdapterProjectionService.task_state(record)` covers `QUEUED`, `RUNNING`, `APPROVAL_REQUIRED`, `DONE`, `FAILED`, `REJECTED`, and `BLOCKED`.
- `AdapterProjectionService.task_record_view(record)` preserves queue `task_id`, queue `status`, execution metadata, mismatches, prompt/error previews, and sanitized result/artifact payloads.
- `AdapterProjectionService.artifact_manifest(path)` reads only allowlisted basenames, handles missing optional files, fails closed on invalid JSON, omits symlink escapes, and includes preview metadata.
- `AdapterProjectionService.artifact_views(record)` and `sanitize_task_record(record)` preserve current category and redaction behavior.

## Compatibility Tests

Update `tests/test_a2a_gateway_contract.py` to prove representative old helper calls delegate to the service:
- descriptor helper equals service descriptor.
- envelope helper equals service envelope.
- task record helper equals service task record view for a fixture with artifact metadata.
- artifact manifest helper equals service artifact manifest for a fixture artifact directory.

Do not duplicate every canonical service test in the facade file; keep full behavior coverage on the new service.

## Static Tests

Update `tests/test_a2a_gateway_contract_static.py` or add a new static test to scan:
- `hermes_agent_gateway/adapter_projection_service.py`
- `hermes_agent_gateway/a2a_gateway_contract.py`
- relevant public docs.

Forbidden categories:
- endpoint names and route-shaped tokens.
- HTTP framework imports or route registration tokens.
- streaming/SSE/subscribe/push notification tokens.
- AgentCard serving or extended-card tokens.
- A2A compatibility/support/server claims in public docs.
- private runner/channel field leaks already guarded today.

## Regression Tests

Run:

```bash
uv run pytest tests/test_adapter_projection_service.py tests/test_a2a_gateway_contract.py tests/test_a2a_gateway_contract_static.py
uv run pytest tests/test_queue.py tests/test_task_service.py tests/test_scheduler_integration.py
uv run pytest
python -m compileall hermes_agent_gateway tests
```

Then run static grep:

```bash
rg -n "message:send|message/send|message:stream|message/stream|text/event-stream|pushNotificationConfig|agent/getAuthenticatedExtendedCard|AgentCard|A2A-compatible|a2a-compatible|supports A2A|full A2A|A2A server|serves A2A|exposes A2A|implements A2A|A2A support|FastAPI|Flask|APIRouter|route\\(" hermes_agent_gateway tests docs
```

## Stop Conditions

- Stop and replan if the extraction requires endpoint/schema/transport concepts to name the service.
- Stop and replan if the compatibility facade creates circular imports that cannot be resolved without broad architecture churn.
- Stop and replan if static gates conflict with required docs rather than catching accidental claims.
