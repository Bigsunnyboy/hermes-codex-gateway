from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_FILES = [ROOT / "hermes_agent_gateway" / "a2a_gateway_contract.py"]
PUBLIC_DOCS = [
    ROOT / "README.md",
    ROOT / "OPERATIONS.md",
    ROOT / "docs" / "A2A_FACING_GATEWAY_CONTRACT_PLAN.md",
    ROOT / "docs" / "HERMES_AGENT_GATEWAY_ARCHITECTURE_PLAN.md",
]


def test_a2a_contract_module_does_not_add_endpoint_or_transport_tokens() -> None:
    forbidden = [
        "message" + ":send",
        "message" + "/send",
        "message" + ":stream",
        "message" + "/stream",
        "/v1" + "/tasks",
        "/tasks" + "/",
        "tasks" + "/cancel",
        "push" + "NotificationConfig",
        "agent/get" + "AuthenticatedExtendedCard",
        "text/event-" + "stream",
    ]

    for path in IMPLEMENTATION_FILES:
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in content


def test_public_docs_do_not_claim_protocol_compatibility() -> None:
    forbidden_claims = [
        "A2A" + "-compatible",
        "a2a" + "-compatible",
        "supports " + "A2A",
        "full " + "A2A",
        "A2A " + "server",
    ]

    for path in PUBLIC_DOCS:
        content = path.read_text(encoding="utf-8")
        for claim in forbidden_claims:
            assert claim not in content


def test_a2a_contract_module_does_not_leak_private_runner_or_channel_fields() -> None:
    forbidden = [
        "Codex" + "CliRunner",
        "codex" + "_executable",
        "feishu" + "_router",
        "event" + ".message_id",
        "event" + ".source",
        "chat" + "_id",
        "approval" + "_card",
    ]

    for path in IMPLEMENTATION_FILES:
        content = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in content
