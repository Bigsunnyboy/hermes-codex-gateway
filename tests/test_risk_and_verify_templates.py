from hermes_local_agent_gateway.risk_policy import assess_task_risk
from hermes_local_agent_gateway.verify_templates import expand_verify_templates


def test_write_risk_classifies_docs_task_as_medium_when_verified() -> None:
    risk = assess_task_risk(
        mode="write",
        prompt="Update README documentation only.",
        verify_commands=["pytest"],
    )

    assert risk["level"] == "medium"
    assert risk["approval_required"] is True
    assert risk["blocked"] is False


def test_write_risk_blocks_destructive_sensitive_prompt() -> None:
    risk = assess_task_risk(
        mode="write",
        prompt="Delete .env and credentials files, then git push --force.",
        verify_commands=["pytest"],
    )

    assert risk["level"] == "critical"
    assert risk["blocked"] is True
    assert "sensitive" in " ".join(risk["reasons"]).lower()


def test_write_risk_treats_sudo_as_reviewable_not_blocked() -> None:
    risk = assess_task_risk(
        mode="write",
        prompt="Document how to use sudo for a local service restart.",
        verify_commands=["pytest"],
    )

    assert risk["level"] == "high"
    assert risk["approval_required"] is True
    assert risk["blocked"] is False
    assert "privileged" in " ".join(risk["reasons"]).lower()


def test_write_risk_blocks_governance_path_references() -> None:
    risk = assess_task_risk(
        mode="write",
        prompt="Change gateway internals.",
        verify_commands=["pytest"],
        allowed_paths=[".hermes/plugins/hermes-codex-gateway/"],
    )

    assert risk["level"] == "critical"
    assert risk["blocked"] is True
    assert "governance" in " ".join(risk["reasons"]).lower()


def test_verify_templates_expand_named_templates_and_safe_file_checks() -> None:
    commands = expand_verify_templates(["pytest", "ruff", "file:generated.txt"])

    assert commands == ["pytest", "ruff", "test -f generated.txt"]
