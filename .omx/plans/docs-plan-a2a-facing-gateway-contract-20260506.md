# Docs Plan: A2A-Facing Gateway Contract

Date: 2026-05-06
Status: consensus-approved planning artifact
Scope: documentation planning only

## Goal

Document the A2A-facing Gateway Contract as a future internal mapping boundary
without adding endpoint instructions, compatibility claims, SDK guidance, or
runtime behavior.

## Deliverables

1. Reconcile or supersede the existing
   `docs/A2A_FACING_GATEWAY_CONTRACT_PLAN.md` with a focused contract
   document, likely `docs/A2A_FACING_GATEWAY_CONTRACT.md`, in a future
   implementation phase.
2. Update `docs/RUNNER_CONTRACT.md` only if needed to cross-reference that
   enabled runner capabilities are the source for future A2A-facing capability
   views.
3. Update `docs/CHANNEL_CONTRACT.md` only if needed to cross-reference that
   channel boundary shapes are the source for future A2A-facing actor/delivery
   context.
4. Review public docs for language that could imply current A2A endpoint
   compatibility.
5. Preserve planning/reference-only wording for A2A HTTP+JSON endpoints,
   streaming events, subscriptions, push notifications, and AgentCard
   publication.

## Required Wording Posture

Use:

- "future A2A adapter";
- "A2A-facing internal mapping contract";
- "maps Gateway Core state toward A2A concepts";
- "no A2A endpoint is implemented in this phase";
- "no A2A compatibility or conformance claim";
- "advertised capabilities must derive from enabled runner/channel/gateway
  capabilities."

Avoid:

- "A2A-compatible";
- "full A2A";
- "supports A2A";
- "A2A server";
- "A2A endpoint";
- "AgentCard is published";
- "streaming is supported";
- "default runner";
- any wording that presents reserved runners as executable support.

## Contract Sections To Add Later

- Purpose and non-goals.
- Boundary ownership:
  - Gateway Core;
  - future A2A adapter;
  - runner registry;
  - channel adapters.
- Capability and skill mapping.
- Message envelope mapping.
- Task status semantic mapping.
- Artifact reference mapping.
- Candidate event semantics for later streaming support.
- Deferred protocol decisions:
  - A2A binding/version;
  - auth and security scheme presentation;
  - exact `TaskState` enum mapping;
  - streaming/subscription support;
  - cancellation behavior;
  - push notification support.
- Verification and forbidden-claim gates.

## Acceptance Criteria

- Docs clearly state that the phase is mapping-contract planning, not endpoint
  implementation.
- Docs do not claim A2A compatibility, endpoint support, streaming support,
  subscription support, push notification support, or AgentCard publication.
- Docs identify `enabled_runner_ids()` and `RunnerCapabilities` as sources for
  future runner capability advertisement.
- Docs identify enabled channel identity plus channel boundary shapes as sources
  for actor/delivery context, without depending on Feishu/Lark raw event
  internals or implying a richer channel capability registry already exists.
- Docs preserve Gateway Core ownership of approval, risk, path guard,
  verification, artifacts, and audit.
- Docs identify unresolved protocol decisions as follow-ups.

## Verification

Suggested docs gate:

```bash
rg -n "A2A-compatible|a2a-compatible|full A2A|supports A2A|A2A server|A2A endpoint|AgentCard is published|streaming is supported|default runner" \
  README.md OPERATIONS.md docs skills
```

Expected:
- no compatibility or implementation claims except in explicit rejected,
  deferred, future, or not-implemented context.

Suggested positive gate:

```bash
rg -n "future A2A adapter|A2A-facing internal mapping contract|no A2A endpoint|no A2A compatibility|enabled runner" \
  docs .omx/plans
```

Expected:
- the new contract docs and planning artifacts contain clear future/deferred
  posture language.
