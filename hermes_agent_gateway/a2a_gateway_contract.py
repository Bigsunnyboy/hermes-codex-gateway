from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .adapter_projection_service import (
    EVENT_SEMANTICS,
    AdapterProjectionService,
    GatewayActorRef,
    GatewayAgentDescriptor,
    GatewayArtifactView,
    GatewayGovernanceMetadata,
    GatewayMessageEnvelope,
    GatewaySkillView,
    GatewayTaskStateView,
    ProtocolCapabilityPosture,
    RunnerCapabilityView,
)


_SERVICE = AdapterProjectionService()


def build_gateway_agent_descriptor() -> GatewayAgentDescriptor:
    return _SERVICE.gateway_descriptor()


def normalize_message_envelope(payload: Mapping[str, Any]) -> GatewayMessageEnvelope:
    return _SERVICE.normalize_adapter_message_envelope(payload, actor_source="a2a")


def gateway_task_state_view(record: Mapping[str, Any]) -> GatewayTaskStateView:
    return _SERVICE.task_state(record)


def gateway_message_payload(envelope: GatewayMessageEnvelope) -> dict[str, Any]:
    return _SERVICE.message_payload(envelope)


def sanitize_task_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return _SERVICE.sanitize_task_record(record)


def artifact_views(record: Mapping[str, Any]) -> tuple[GatewayArtifactView, ...]:
    return _SERVICE.artifact_views(record)


def artifact_manifest(artifact_dir: str | Path) -> dict[str, Any]:
    return _SERVICE.artifact_manifest(artifact_dir)


def gateway_task_record_view(record: Mapping[str, Any]) -> dict[str, Any]:
    return _SERVICE.task_record_view(record)
