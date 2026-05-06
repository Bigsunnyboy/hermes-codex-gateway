# Channel Adapter Boundary Plan

Date: 2026-05-06
Status: consensus candidate

## Goal

Introduce a thin Channel Adapter Boundary so Feishu/Lark is the first concrete
channel adapter, not Gateway Core. The phase preserves current behavior and
does not add any new platform adapter or A2A endpoint.

## Decision

Create explicit neutral channel shapes:

- `ChannelActor`
- `DeliveryTarget`
- `ApprovalCardRef`
- `ChannelCommand`

Keep Feishu/Lark as the only concrete facade. Do not add a registry, abstract
base class hierarchy, discovery layer, new adapter, queue migration, or A2A
endpoint in this phase.

## Boundary

Gateway-facing code should use neutral fields:

- `channel`
- `conversation_id`
- `reply_to_message_id`
- `actor_id`
- `display_name`
- `message_id`

`hermes_agent_gateway/channel_boundary.py` should own only neutral shapes and
queue serialization helpers. Raw event extraction helpers such as
`channel_command_from_event` belong in the Feishu/Lark facade, not the neutral
boundary module.

Serialized queue compatibility fields remain unchanged:

- `delivery.platform`
- `delivery.chat_id`
- `delivery.reply_to`
- `delivery.approval_card.platform`
- `delivery.approval_card.chat_id`
- `delivery.approval_card.message_id`
- optional `delivery.approval_card.reply_to`
- `delivery.approval_card.kind`

## Required Runtime Wiring

The Feishu/Lark facade must expose sender/card-updater callables for plugin
runtime paths. Root plugin handlers must inject those callables into scheduler
and delivery functions. `delivery.py` must not import live Hermes runtime
internals such as `gateway.config`, `gateway.run`, or `model_tools`. Root tool
handlers should source the live gateway from handler kwargs before constructing
facade callables.

## Implementation Order

1. Add Feishu behavior characterization and Lark parity tests.
2. Add `hermes_agent_gateway/channel_boundary.py` with neutral shapes and queue
   serialization helpers.
3. Refactor `hermes_agent_gateway/feishu_router.py` so raw event extraction,
   adapter lookup, text sends, card sends, and card edits are inside the
   Feishu/Lark facade.
4. Refactor `hermes_agent_gateway/delivery.py` to use boundary helpers and
   injected sender/card-updater callables.
5. Wire root plugin handlers to pass facade callables into scheduler and
   delivery paths.
6. Update `docs/CHANNEL_CONTRACT.md` and run static coupling gates.

## Acceptance Criteria

- Feishu and Lark both pass enqueue, ack, approval card, approve/reject/status,
  card update, final delivery, and fallback delivery tests.
- Queue serialization remains byte-shape compatible for existing fields.
- Root hooks remain compatible: `pre_gateway_dispatch` and
  `feishu_card_action_response`.
- Public tool names stay agent-generic.
- No live platform adapter internals remain in `delivery.py`.
- No new channel adapter, registry, A2A endpoint, or queue migration is added.

## Verification

Focused:

```bash
PYTHONPATH=. python3 -m pytest \
  tests/test_feishu_route.py \
  tests/test_delivery.py \
  tests/test_scheduler_integration.py \
  tests/test_plugin_registration.py \
  -q
```

Full:

```bash
PYTHONPATH=. python3 -m pytest tests -q
python3 -m compileall -q hermes_agent_gateway
scripts/sanitize-check.sh
git diff --check
```

Static gate:

```bash
rg -n "event\\.source|event\\.message_id|_feishu_send_with_retry|edit_interactive_card|from gateway\\.config|from gateway\\.run|from model_tools|_gateway_runner_ref" \
  hermes_agent_gateway __init__.py \
  -g '!hermes_agent_gateway/feishu_router.py'
```

Expected result: no matches.
