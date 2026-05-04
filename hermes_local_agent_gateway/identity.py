from __future__ import annotations

import re


SAFE_ID_PATTERN = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_id(value: str) -> str:
    cleaned = SAFE_ID_PATTERN.sub("-", value.strip()).strip(".-")
    if not cleaned:
        raise ValueError("identifier cannot be empty")
    return cleaned[:80]
