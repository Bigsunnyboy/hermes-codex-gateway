# PRD: Adapter-Facing Projection Service Boundary

## Outcome

Future adapters depend on one Gateway-owned internal projection service for descriptor, envelope, task state, task record, artifact, and sanitized view projection. They do not depend on queue files, artifact directories, runner-private fields, Feishu/Lark fields, or scattered A2A-facing helper functions.

This batch is a refactor and boundary-hardening batch. It does not implement endpoints, transport routes, A2A SDK integration, streaming, subscribe, AgentCard serving, public schemas, or compatibility claims.

## Scope

Implement or extract:
- `hermes_agent_gateway/adapter_projection_service.py` as the canonical internal service boundary.
- A thin `hermes_agent_gateway/a2a_gateway_contract.py` compatibility facade for existing helper names.
- Canonical service tests in `tests/test_adapter_projection_service.py`.
- Compatibility/static tests in existing A2A contract test files.
- Docs that identify the new service as the only future adapter-facing dependency.

## Functional Requirements

- The service exposes descriptor projection equivalent to current `build_gateway_agent_descriptor`.
- The service exposes message envelope normalization and payload projection equivalent to current `normalize_message_envelope` and `gateway_message_payload`, except actor-source validation is neutral at the canonical service layer.
- The A2A-facing compatibility facade preserves current `actor.source == "a2a"` validation while delegating projection behavior to the service.
- The service exposes task lifecycle projection equivalent to current `gateway_task_state_view`, including future-binding flags for approval/rejected/blocked states.
- The service exposes task record projection equivalent to current `gateway_task_record_view`.
- The service exposes task-record projection as the future adapter-facing entrypoint.
- The service keeps artifact manifest projection equivalent to current `artifact_manifest` as internal/testable plumbing behind task-record views; future adapters should not depend directly on artifact directory reads.
- The service exposes artifact category projection equivalent to current `artifact_views`.
- The service exposes sanitization equivalent to current `sanitize_task_record`.
- Existing A2A-facing helper names continue to work by delegating to the service.

## Boundary Requirements

- The service is projection-only and transport-neutral.
- The service accepts mappings and returns sanitized adapter-facing views; it does not own queue persistence, scheduling, delivery, route registration, or network serving.
- Direct artifact path reads remain internal service plumbing for composing task-record views and tests, not a future adapter dependency.
- Queue `task_id` remains the task-facing identity.
- Queue `status` remains lifecycle-authoritative when result or artifact metadata disagrees.
- Execution task ids remain metadata only.
- Artifact reads remain fixed-basename, contained, bounded, sanitized, and symlink-escape resistant.
- Static gates cover both the new service and compatibility facade.
- Static gates split implementation-token bans from documentation-claim bans so non-goal/deferred-work wording remains allowed while compatibility claims remain forbidden.

## Documentation Requirements

- Docs say future adapters depend on the adapter-facing projection service.
- Docs may say A2A is a future adapter consumer direction.
- Docs must not claim A2A compatibility, A2A support, endpoint serving, AgentCard serving, streaming, subscribe, or SDK integration.
- Docs may mention endpoints, AgentCard, streaming, or subscribe only as explicit non-goals or deferred follow-ups.

## Non-Goals

- No endpoints, route handlers, transport bindings, SDK dependencies, streaming, subscribe, push notifications, AgentCard serving, public schemas, task-listing endpoints, cancel endpoints, or compatibility claims.
- No queue storage migration.
- No scheduler, approval, risk, path guard, verification, artifact capture, audit, delivery, runner, or channel behavior changes.
- No new runner or channel adapter.

## Acceptance Criteria

- `tests/test_adapter_projection_service.py` imports the canonical service and covers descriptor, envelope, lifecycle, task record, artifact, and sanitization behavior.
- Existing A2A-facing helper tests still pass or are adjusted to verify facade equivalence.
- Static tests scan all projection implementation files and docs for forbidden tokens/claims.
- Docs identify the service boundary and preserve endpoint-free posture.
- Targeted tests, regression tests, full pytest, compileall, and static grep pass.
