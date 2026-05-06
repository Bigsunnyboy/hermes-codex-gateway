from hermes_agent_gateway.channel_boundary import (
    ApprovalCardRef,
    DeliveryTarget,
    approval_card_from_queue,
    approval_card_to_queue,
    delivery_target_from_queue,
    delivery_target_to_queue,
    normalize_channel,
)


def test_delivery_target_round_trips_existing_queue_shape() -> None:
    target = DeliveryTarget(channel="feishu", conversation_id="oc_123", reply_to_message_id="om_msg")

    queued = delivery_target_to_queue(target)

    assert queued == {"platform": "feishu", "chat_id": "oc_123", "reply_to": "om_msg"}
    assert delivery_target_from_queue(queued) == target


def test_lark_delivery_target_round_trips_existing_queue_shape_without_reply() -> None:
    target = DeliveryTarget(channel="lark", conversation_id="oc_lark")

    queued = delivery_target_to_queue(target)

    assert queued == {"platform": "lark", "chat_id": "oc_lark"}
    assert delivery_target_from_queue(queued) == target


def test_approval_card_ref_round_trips_existing_queue_shape() -> None:
    ref = ApprovalCardRef(
        channel="lark",
        conversation_id="oc_lark",
        message_id="om_card",
        reply_to_message_id="om_original",
    )

    queued = approval_card_to_queue(ref)

    assert queued == {
        "platform": "lark",
        "chat_id": "oc_lark",
        "message_id": "om_card",
        "reply_to": "om_original",
        "kind": "agent_write_approval",
    }
    assert approval_card_from_queue(queued) == ref


def test_incomplete_queue_boundary_records_return_none() -> None:
    assert delivery_target_from_queue({"platform": "feishu"}) is None
    assert approval_card_from_queue({"platform": "feishu", "chat_id": "oc_123"}) is None


def test_normalize_channel_accepts_only_enabled_channel_values() -> None:
    assert normalize_channel(" Feishu ") == "feishu"
    assert normalize_channel("LARK") == "lark"

    try:
        normalize_channel("slack")
    except ValueError as exc:
        assert "enabled channel" in str(exc)
    else:
        raise AssertionError("expected slack to be rejected")
