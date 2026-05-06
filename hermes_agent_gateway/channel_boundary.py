from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

ChannelName = Literal["feishu", "lark"]

_ENABLED_CHANNELS = {"feishu", "lark"}


@dataclass(frozen=True)
class ChannelActor:
    channel: ChannelName
    actor_id: str | None
    display_name: str | None


@dataclass(frozen=True)
class DeliveryTarget:
    channel: ChannelName
    conversation_id: str
    reply_to_message_id: str | None = None


@dataclass(frozen=True)
class ApprovalCardRef:
    channel: ChannelName
    conversation_id: str
    message_id: str
    reply_to_message_id: str | None = None
    kind: Literal["agent_write_approval"] = "agent_write_approval"


@dataclass(frozen=True)
class ChannelCommand:
    channel: ChannelName
    text: str
    actor: ChannelActor
    delivery: DeliveryTarget | None
    message_id: str | None


def normalize_channel(value: Any) -> ChannelName:
    channel = str(getattr(value, "value", value) or "").strip().lower()
    if channel not in _ENABLED_CHANNELS:
        raise ValueError("channel is required and must be an enabled channel: feishu, lark")
    return cast(ChannelName, channel)


def delivery_target_from_queue(value: Any) -> DeliveryTarget | None:
    if not isinstance(value, dict):
        return None
    try:
        channel = normalize_channel(value.get("platform"))
    except ValueError:
        return None
    conversation_id = str(value.get("chat_id") or "").strip()
    if not conversation_id:
        return None
    reply_to = str(value.get("reply_to") or "").strip() or None
    return DeliveryTarget(
        channel=channel,
        conversation_id=conversation_id,
        reply_to_message_id=reply_to,
    )


def delivery_target_to_queue(target: DeliveryTarget) -> dict[str, str]:
    queued = {
        "platform": target.channel,
        "chat_id": target.conversation_id,
    }
    if target.reply_to_message_id:
        queued["reply_to"] = target.reply_to_message_id
    return queued


def approval_card_from_queue(value: Any) -> ApprovalCardRef | None:
    if not isinstance(value, dict):
        return None
    try:
        channel = normalize_channel(value.get("platform"))
    except ValueError:
        return None
    conversation_id = str(value.get("chat_id") or "").strip()
    message_id = str(value.get("message_id") or "").strip()
    if not conversation_id or not message_id:
        return None
    reply_to = str(value.get("reply_to") or "").strip() or None
    kind = str(value.get("kind") or "agent_write_approval").strip()
    if kind != "agent_write_approval":
        return None
    return ApprovalCardRef(
        channel=channel,
        conversation_id=conversation_id,
        message_id=message_id,
        reply_to_message_id=reply_to,
    )


def approval_card_to_queue(ref: ApprovalCardRef) -> dict[str, str]:
    queued = {
        "platform": ref.channel,
        "chat_id": ref.conversation_id,
        "message_id": ref.message_id,
    }
    if ref.reply_to_message_id:
        queued["reply_to"] = ref.reply_to_message_id
    queued["kind"] = ref.kind
    return queued
