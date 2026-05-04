from __future__ import annotations

import re


_SENSITIVE_PATTERN = re.compile(
    r"(?i)(^|[\s/])(\.env|auth\.json|credentials?[^\s]*|[^\s]*secret[^\s]*|[^\s]*\.key)(?=$|[\s,.;/])"
)
_DESTRUCTIVE_PATTERN = re.compile(
    r"(?i)(rm\s+-rf|git\s+push\s+--force|drop\s+database|delete\s+.*database|chmod\s+777)"
)
_PRIVILEGED_PATTERN = re.compile(r"(?i)\bsudo\s+")
_DOCS_TESTS_PATTERN = re.compile(r"(?i)(readme|docs?/|documentation|test|pytest|spec)")
_GOVERNANCE_PATH_PATTERN = re.compile(
    r"(?i)(^|[\s,;:/])("
    r"\.git(?:/|$)|"
    r"\.codex(?:/|$)|"
    r"\.omx(?:/|$)|"
    r"\.hermes(?:/|$)|"
    r"hermes-agent(?:/|$)|"
    r"hermes-codex-gateway(?:/|$)"
    r")"
)


def assess_task_risk(
    *,
    mode: str,
    prompt: str,
    verify_commands: list[str] | None = None,
    allowed_paths: list[str] | None = None,
) -> dict[str, object]:
    reasons: list[str] = []
    clean_mode = (mode or "read").strip().lower()
    text = prompt or ""
    verify = [command for command in verify_commands or [] if command.strip()]
    allowed = [path for path in allowed_paths or [] if path.strip()]

    if clean_mode == "read":
        return {
            "level": "low",
            "approval_required": False,
            "blocked": False,
            "reasons": ["read-only sandbox"],
        }

    if _SENSITIVE_PATTERN.search(text):
        reasons.append("sensitive path or credential reference")
    if _GOVERNANCE_PATH_PATTERN.search(text) or any(_GOVERNANCE_PATH_PATTERN.search(path) for path in allowed):
        reasons.append("protected governance path reference")
    if _DESTRUCTIVE_PATTERN.search(text):
        reasons.append("destructive shell/git/database intent")
    if reasons:
        return {
            "level": "critical",
            "approval_required": True,
            "blocked": True,
            "reasons": reasons,
        }

    if not verify:
        return {
            "level": "high",
            "approval_required": True,
            "blocked": False,
            "reasons": ["write task has no verification template or command"],
        }

    if _PRIVILEGED_PATTERN.search(text):
        return {
            "level": "high",
            "approval_required": True,
            "blocked": False,
            "reasons": ["privileged command reference requires review"],
        }

    if _DOCS_TESTS_PATTERN.search(text):
        return {
            "level": "medium",
            "approval_required": True,
            "blocked": False,
            "reasons": ["write task appears limited to docs or tests and has verification"],
        }

    return {
        "level": "high",
        "approval_required": True,
        "blocked": False,
        "reasons": ["write task can modify source code"],
    }
