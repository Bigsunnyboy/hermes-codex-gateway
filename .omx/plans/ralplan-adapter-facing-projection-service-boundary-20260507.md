# RALPLAN-DR: Adapter-Facing Projection Service Boundary

Task:
- Plan the next larger implementation batch after real queue/artifact projection at HEAD `5d6ba3e`.
- Lift current A2A-facing projection helpers into the only internal service boundary future adapters may depend on.
- Add tests and docs while staying endpoint-free and adapter-facing.

Evidence:
- Current helper implementation is concentrated in `hermes_agent_gateway/a2a_gateway_contract.py`.
- Existing public helpers include `build_gateway_agent_descriptor`, `normalize_message_envelope`, `gateway_task_state_view`, `artifact_manifest`, and `gateway_task_record_view`.
- `tests/test_a2a_gateway_contract.py` covers descriptor, envelope, lifecycle, sanitization, artifact manifest, and queue/artifact precedence behavior.
- `tests/test_a2a_gateway_contract_static.py` blocks endpoint/transport tokens, protocol compatibility claims, and private runner/channel field leakage.
- Existing docs are `docs/A2A_FACING_GATEWAY_CONTRACT_PLAN.md`, `docs/A2A_REAL_TASK_ARTIFACT_VIEWS_PLAN.md`, and `docs/HERMES_AGENT_GATEWAY_ARCHITECTURE_PLAN.md`.
- Context snapshot: `.omx/context/adapter-facing-projection-service-boundary-20260507T013339Z.md`.

## RALPLAN-DR Summary

### Principles

1. Adapter dependency is narrow: future adapters depend on one named projection service, not queue files, artifact files, runner internals, or scattered helper functions.
2. Gateway Core remains authoritative: queue lifecycle, governance, approval, risk, verification, artifacts, and audit stay owned by core services.
3. Projection is transport-neutral: the boundary may prepare adapter-facing internal views, but must not select endpoint routes, SDK objects, streaming semantics, AgentCard serving, or compatibility posture.
4. Preserve existing behavior while relocating ownership: current helper outputs should remain available through compatibility wrappers unless callers/tests are intentionally moved in the same batch.
5. Static gates define the red lines: no endpoint, transport, subscribe, streaming, SDK, AgentCard-serving, or A2A compatibility claims enter code or docs.

### Decision Drivers

1. Future adapter work needs one stable internal service contract before any transport binding can be planned.
2. The batch should be substantive enough for Ralph to execute as a coherent boundary refactor, not another tiny helper addition.
3. The refactor must avoid broad architecture churn and keep endpoint/protocol decisions deferred.

### Viable Options

#### Option A: Create `adapter_projection_service.py` And Keep `a2a_gateway_contract.py` As A Compatibility Facade

Pros:
- Establishes a clearly named adapter-facing service boundary.
- Future adapters can import one service module without inheriting A2A-specific helper naming.
- Existing tests and callers can continue through compatibility wrappers during the transition.
- Keeps the batch endpoint-free and mostly mechanical around already-tested behavior.

Cons:
- Temporarily leaves two module names in play.
- Requires static tests to cover both the new service and the old facade.
- Naming must be disciplined so the service does not become a generic adapter framework.

#### Option B: Rename `a2a_gateway_contract.py` In Place To A Generic Projection Module

Pros:
- Removes A2A-specific module naming immediately.
- Cleaner long-term import surface if all callers migrate in one batch.

Cons:
- More disruptive to tests and docs.
- Higher risk of losing historical A2A-facing guardrails during rename.
- Harder to keep the diff reviewable because module move, import rewrite, and service API design happen together.

#### Option C: Keep Current Module And Add A Service Class Inside It

Pros:
- Smallest code movement.
- Existing tests barely change.

Cons:
- Does not fully satisfy "only internal service boundary" because the public internal import remains a scattered helper module.
- Future non-A2A adapters would still depend on A2A-named code.
- Leaves boundary ownership ambiguous.

Chosen option:
- Choose Option A. Add a new Gateway-owned adapter-facing projection service module, move or delegate the implementation there, and keep `a2a_gateway_contract.py` as a thin deprecated/internal compatibility facade for existing A2A-facing names.

Rejected alternatives:
- Do not add endpoint-shaped adapters or route/controller files.
- Do not create a generic plugin/adapter framework in this batch.
- Do not make `queue.py`, `artifacts.py`, runner modules, Feishu/Lark modules, or future transport adapters the projection dependency.

## Concrete Implementation Batch Scope

### Likely Files Touched

Code:
- `hermes_agent_gateway/adapter_projection_service.py` or similarly explicit Gateway-owned name.
- `hermes_agent_gateway/a2a_gateway_contract.py` as a thin compatibility facade that re-exports or delegates to the new service boundary.
- Optionally `hermes_agent_gateway/__init__.py` only if the repository already exposes internal module exports there; otherwise leave it untouched.

Tests:
- `tests/test_adapter_projection_service.py` for the new canonical boundary.
- `tests/test_a2a_gateway_contract.py` to prove compatibility wrappers still produce the same behavior or to reduce direct coverage if duplicated by canonical tests.
- `tests/test_a2a_gateway_contract_static.py` or a renamed/expanded static test that scans both modules and docs for forbidden claims/tokens.

Docs:
- `docs/A2A_FACING_GATEWAY_CONTRACT_PLAN.md`
- `docs/A2A_REAL_TASK_ARTIFACT_VIEWS_PLAN.md`
- `docs/HERMES_AGENT_GATEWAY_ARCHITECTURE_PLAN.md`
- Optional new doc `docs/ADAPTER_FACING_PROJECTION_SERVICE_BOUNDARY_PLAN.md` if the existing docs become too crowded.

Planning artifacts:
- `.omx/plans/prd-adapter-facing-projection-service-boundary-20260507.md`
- `.omx/plans/test-spec-adapter-facing-projection-service-boundary-20260507.md`

### Canonical Service Shape

Implement a single internal service boundary with a narrow API. Exact names can be adjusted to fit local style, but the boundary should make these responsibilities explicit:

- descriptor projection: current `build_gateway_agent_descriptor` behavior.
- message/envelope normalization: current `normalize_message_envelope` and `gateway_message_payload` behavior.
- task lifecycle projection: current `gateway_task_state_view` and queue-status precedence behavior.
- task record projection: current `gateway_task_record_view` behavior.
- artifact projection: current `artifact_manifest`, `artifact_views`, and sanitization behavior.

Recommended low-churn shape:

```text
AdapterProjectionService
  .gateway_descriptor()
  .normalize_message_envelope(payload)
  .message_payload(envelope)
  .task_state(record)
  .task_record_view(record)
  .artifact_manifest(artifact_dir)
  .artifact_views(record)
  .sanitize_task_record(record)
```

The module may also export dataclasses/types currently in `a2a_gateway_contract.py` if tests and docs need stable names. Keep types Gateway/adapter-facing, not endpoint or SDK-facing.

Compatibility facade:
- Keep existing helper function names in `a2a_gateway_contract.py`.
- Each helper delegates to a default service instance or function in the new service module.
- Mark the facade as internal A2A-facing compatibility in docs/comments without claiming public API stability.

### Implementation Steps For Ralph

1. Add regression tests against a canonical service import.
   - Cover descriptor, envelope normalization, lifecycle mapping, queue/artifact task record projection, artifact manifest containment/truncation, and sanitization through `AdapterProjectionService`.
   - Include a direct equivalence test proving existing `a2a_gateway_contract` helper wrappers return the same values as the service for representative fixtures.

2. Create the new service module and move projection ownership.
   - Move dataclasses/constants/helpers or import them from the old module only if avoiding circular imports remains simple.
   - Prefer the new module as the implementation owner and make `a2a_gateway_contract.py` delegate outward.
   - Preserve current behavior and output shapes unless a test intentionally tightens the boundary.

3. Add service-level entrypoints for future adapter use, not transport use.
   - Provide a default service instance or factory if that matches local style.
   - Keep queue access out of the service unless it is injected as records; the service should project mappings/paths, not own queue persistence.
   - Do not add list/get endpoint semantics. If a helper accepts records, it projects them only.

4. Strengthen static gates.
   - Scan the new module and old facade for endpoint/transport tokens.
   - Keep compatibility-claim checks across public docs.
   - Add assertions that future adapters should not import queue/artifact internals directly when tests can enforce this cheaply without brittle repo-wide import bans.

5. Update docs.
   - State that the adapter-facing projection service is now the only internal dependency future adapters should consume.
   - Clarify that A2A-facing docs refer to one future adapter consumer of the service, not the service identity.
   - Preserve explicit non-goals: no endpoints, transport routes, SDK, streaming, subscribe, AgentCard serving, public schemas, or compatibility claims.

6. Run verification and commit.
   - Run targeted tests first, then full tests/static grep.
   - Commit with the repository Lore Commit Protocol after verification.

## Acceptance Criteria

- A new internal adapter-facing projection service module exists and owns the implementation of descriptor, envelope, lifecycle, task record, artifact, and sanitization projection.
- Existing `a2a_gateway_contract.py` helper names remain available as a thin compatibility facade or are intentionally migrated with tests proving no behavior regression.
- Future adapter-facing docs point adapters at the service boundary rather than queue files, artifact directories, runner internals, Feishu/Lark fields, or scattered A2A helpers.
- Tests prove the canonical service returns the same descriptor/envelope/task/artifact shapes currently covered by `tests/test_a2a_gateway_contract.py`.
- Tests prove queue `task_id` and queue `status` remain task-facing/lifecycle-authoritative when execution artifacts disagree.
- Tests prove artifact reads remain fixed-basename, contained, bounded, sanitized, and symlink-escape resistant.
- Static tests cover the new service module and old facade for endpoint/transport/SDK/streaming/subscribe/AgentCard-serving tokens.
- Public docs do not claim A2A compatibility, A2A support, A2A server behavior, endpoint serving, or AgentCard exposure.
- No endpoint files, transport routes, A2A SDK dependency, streaming/subscription behavior, task-listing endpoint semantics, or compatibility claims are added.

## Verification Commands

Run after implementation:

```bash
uv run pytest tests/test_adapter_projection_service.py tests/test_a2a_gateway_contract.py tests/test_a2a_gateway_contract_static.py
uv run pytest tests/test_queue.py tests/test_task_service.py tests/test_scheduler_integration.py
uv run pytest
python -m compileall hermes_agent_gateway tests
rg -n "message:send|message/send|message:stream|message/stream|text/event-stream|pushNotificationConfig|agent/getAuthenticatedExtendedCard|AgentCard|A2A-compatible|a2a-compatible|supports A2A|full A2A|A2A server|serves A2A|exposes A2A|implements A2A|A2A support|FastAPI|Flask|APIRouter|route\\(" hermes_agent_gateway tests docs
```

Expected grep behavior:
- The command may print only intentionally forbidden-token test fixtures if the static test stores split tokens to avoid literal matches.
- It must not find forbidden tokens in implementation or public compatibility claims in docs.

## Non-Goals

- No HTTP, JSON-RPC, gRPC, SSE, webhook, subscribe, stream, push notification, cancel, task listing, or transport route implementation.
- No A2A SDK dependency.
- No AgentCard serving, extended card, signed card, or compatibility claim.
- No public schema commitment or endpoint response shape.
- No queue storage migration.
- No scheduler, approval, risk, path guard, verification, artifact capture, audit, delivery, runner, or channel behavior changes.
- No new runner or channel adapter.
- No public claim that Hermes implements, supports, serves, exposes, or is compatible with A2A.

## Risks And Mitigations

- Risk: The new service becomes a broad adapter framework.
  Mitigation: Keep it projection-only; it accepts records/payloads/artifact dirs and returns internal views.
- Risk: Compatibility wrappers hide duplicate ownership.
  Mitigation: Make wrappers one-line delegates and make canonical tests import the new service.
- Risk: A module rename breaks existing A2A-facing tests without improving behavior.
  Mitigation: Move behavior behind the new module first, then adjust tests incrementally.
- Risk: Static gates become brittle.
  Mitigation: Keep forbidden checks focused on endpoint/transport/claim/private-field tokens already guarded today plus the new module path.
- Risk: Docs accidentally overstate protocol posture.
  Mitigation: Repeat the explicit wording: internal adapter-facing projection service only; no A2A endpoints or compatibility.

## Handoff Notes For Ralph

Use the service-boundary refactor as one coherent batch:
- Start test-first by adding `tests/test_adapter_projection_service.py` with current behavior fixtures.
- Then extract/move implementation into `hermes_agent_gateway/adapter_projection_service.py`.
- Keep `a2a_gateway_contract.py` as a compatibility facade so this batch does not become a broad import migration.
- Update docs after tests and code settle so wording matches the actual service shape.
- Run targeted tests, regression tests, full pytest, compileall, and static grep before final report.
- Create a local git commit using the Lore Commit Protocol. Do not push.

Available agent types for follow-up:
- `executor`: implementation/refactor owner, medium reasoning.
- `test-engineer`: canonical service tests and static gates, medium reasoning.
- `writer`: docs and wording posture, high reasoning for claim discipline.
- `verifier`: final evidence pass, high reasoning.
- `code-reviewer`: optional review focused on boundary leakage and endpoint-free constraints, high reasoning.
- `architect` / `critic`: optional if Ralph finds the service naming or boundary shape contentious.

Suggested Ralph path:
- Single-owner Ralph is preferred because the refactor touches shared projection code and tests. Use native subagents only for a parallel docs/static-gate review or final verification after the code shape stabilizes.

Suggested team path if parallelism is explicitly chosen:
- Lane 1 `executor`: new service module and compatibility facade.
- Lane 2 `test-engineer`: canonical service tests and static gates.
- Lane 3 `writer`: docs and PRD/test-spec consistency.
- Lane 4 `verifier`: targeted/full verification and static grep after integration.

Team verification path:
- Team verifier proves targeted service/static tests pass first.
- Then run queue/task/scheduler regression tests.
- Then full pytest and compileall.
- Then static grep for endpoint/transport/compatibility tokens.
- Ralph or a final verifier reviews changed files for endpoint-free scope before shutdown.

## ADR

Decision:
- Introduce a canonical internal adapter-facing projection service and make the current A2A-facing helper module a compatibility facade.

Drivers:
- Future adapters need one stable internal dependency.
- Existing projection behavior is useful but currently named and organized as scattered A2A-facing helpers.
- Endpoint, transport, SDK, streaming, AgentCard, and compatibility decisions remain explicitly deferred.

Alternatives considered:
- Rename `a2a_gateway_contract.py` in place: rejected for higher churn and weaker compatibility during the batch.
- Add a service class inside `a2a_gateway_contract.py`: rejected because future non-A2A adapters would still depend on an A2A-named module.
- Build endpoint/schema scaffolding now: rejected by hard non-goals.

Why chosen:
- It creates the intended service boundary with low behavioral risk, preserves current tests through wrappers, and gives future adapters a clean dependency without implying A2A transport readiness.

Consequences:
- One new internal module becomes the canonical projection surface.
- Old helper names remain temporarily as internal compatibility.
- Static tests must scan both old and new projection surfaces.
- Docs must distinguish adapter-facing service boundary from A2A protocol compatibility.

Follow-ups:
- Later batch may migrate future adapter imports to the service directly and retire the compatibility facade after no internal callers depend on it.
- Later endpoint planning must still choose binding/version/auth/conformance, AgentCard posture, streaming/subscription posture, and final wire state mapping.

## Planner Changelog

- Grounded the plan against HEAD `5d6ba3e`, the current helper module, current tests, static gates, docs, and the adapter-facing context snapshot.
- Selected a larger service-boundary extraction batch rather than endpoint work or another helper-only slice.
- Added Ralph/team handoff guidance while preserving endpoint-free non-goals.
