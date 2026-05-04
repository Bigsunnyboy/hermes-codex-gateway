from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .config import GatewayConfig
from .delivery import CardUpdater, deliver_task_result, AdapterSender, update_task_lifecycle_card
from .queue import FileTaskQueue
from .runner import CodexCliRunner
from .task_service import Runner, create_codex_task


_WORKER_PROMPT_BODY = (
    "Use the Hermes tool run_next_codex_task exactly once; it runs one queued task and "
    "auto-delivers the final result to the original Feishu chat when a delivery target exists. "
    "If it returns EMPTY, reply briefly that the Codex queue is empty. "
    "Do not use terminal or spawn Codex directly."
)
_WORKER_PROMPT_HASH = hashlib.sha256(_WORKER_PROMPT_BODY.encode("utf-8")).hexdigest()[:12]
WORKER_PROMPT_VERSION = f"gateway-worker-prompt:{_WORKER_PROMPT_HASH}"
DEFAULT_WORKER_PROMPT = f"[{WORKER_PROMPT_VERSION}]\n{_WORKER_PROMPT_BODY}"

WAKE_SCRIPT_NAME = "codex_queue_worker_wake.py"
WAKE_SCRIPT = '''from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    hermes_home = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes")))
    queue_root = hermes_home / "agent_queue"
    wake = False
    if queue_root.exists():
        for path in sorted(queue_root.glob("queued_*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if record.get("status") == "QUEUED":
                wake = True
                break
    print(json.dumps({"wakeAgent": wake}, sort_keys=True))


if __name__ == "__main__":
    main()
'''


def run_next_queue_task(
    cfg: GatewayConfig,
    *,
    queue: FileTaskQueue,
    runner: Runner | None = None,
    delivery_sender: AdapterSender | None = None,
    card_updater: CardUpdater | None = None,
) -> dict[str, Any]:
    record = queue.claim_next()
    if record is None:
        return {"status": "EMPTY"}
    update_task_lifecycle_card(queue, record, phase="RUNNING", card_updater=card_updater)

    try:
        payload = record["payload"]
        actual_runner = runner or CodexCliRunner(
            codex_executable=cfg.codex_executable,
            extra_env=cfg.codex_env or {},
            max_output_bytes=cfg.max_output_bytes,
        )
        result = create_codex_task(
            cfg,
            runner=actual_runner,
            repo=payload.get("repo"),
            path=payload.get("path"),
            mode=str(payload.get("mode") or "read"),
            prompt=str(payload.get("prompt") or ""),
            workspace_id=payload.get("workspace_id"),
            codex_session_id=payload.get("codex_session_id"),
            approved=bool(payload.get("approved", False)),
            verify_commands=list(payload.get("verify_commands") or []),
            allowed_paths=list(payload.get("allowed_paths") or []),
        )
        completed = queue.complete(record["task_id"], result)
        return _deliver_if_needed(
            queue,
            completed,
            delivery_sender=delivery_sender,
            card_updater=card_updater,
        )
    except Exception as exc:
        failed = queue.fail(record["task_id"], f"{type(exc).__name__}: {exc}")
        return _deliver_if_needed(
            queue,
            failed,
            delivery_sender=delivery_sender,
            card_updater=card_updater,
        )


def _deliver_if_needed(
    queue: FileTaskQueue,
    record: dict[str, Any],
    *,
    delivery_sender: AdapterSender | None = None,
    card_updater: CardUpdater | None = None,
) -> dict[str, Any]:
    if not (record.get("payload") or {}).get("delivery"):
        return record
    delivery_result = deliver_task_result(
        queue,
        task_id=str(record["task_id"]),
        adapter_sender=delivery_sender,
        card_updater=card_updater,
    )
    updated = dict(queue.get(str(record["task_id"])))
    updated["delivery_result"] = delivery_result
    return updated


def ensure_worker_cron_job(
    *,
    cron_api: Callable[..., str | dict[str, Any]] | None = None,
    name: str,
    schedule: str,
    scripts_dir: Path | None = None,
) -> dict[str, Any]:
    api = cron_api or _load_cron_api()
    ensure_worker_wake_script(scripts_dir)
    existing = _decode(api(action="list"))
    for job in existing.get("jobs", []):
        if job.get("name") == name:
            job_id = job.get("id") or job.get("job_id")
            if (
                not _job_prompt_matches(job)
                or job.get("script") != WAKE_SCRIPT_NAME
                or job.get("enabled_toolsets") != [
                    "hermes_local_agent_gateway"
                ]
            ):
                _decode(
                    api(
                        action="update",
                        job_id=job_id,
                        prompt=DEFAULT_WORKER_PROMPT,
                        script=WAKE_SCRIPT_NAME,
                        enabled_toolsets=["hermes_local_agent_gateway"],
                    )
                )
                return {
                    "created": False,
                    "updated": True,
                    "job_id": job_id,
                    "name": name,
                }
            return {
                "created": False,
                "updated": False,
                "job_id": job_id,
                "name": name,
            }

    created = _decode(
        api(
            action="create",
            name=name,
            schedule=schedule,
            prompt=DEFAULT_WORKER_PROMPT,
            script=WAKE_SCRIPT_NAME,
            enabled_toolsets=["hermes_local_agent_gateway"],
        )
    )
    return {
        "created": True,
        "job_id": created.get("job_id") or (created.get("job") or {}).get("id"),
        "name": name,
        "schedule": schedule,
    }


def ensure_worker_wake_script(scripts_dir: Path | None = None) -> Path:
    root = scripts_dir or _default_scripts_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / WAKE_SCRIPT_NAME
    if not path.exists() or path.read_text(encoding="utf-8") != WAKE_SCRIPT:
        path.write_text(WAKE_SCRIPT, encoding="utf-8")
    return path


def _load_cron_api():
    from tools.cronjob_tools import cronjob

    return cronjob


def _job_prompt_matches(job: dict[str, Any]) -> bool:
    if "prompt" in job:
        return job.get("prompt") == DEFAULT_WORKER_PROMPT
    prompt_preview = job.get("prompt_preview")
    if not isinstance(prompt_preview, str):
        return False
    return prompt_preview.startswith(f"[{WORKER_PROMPT_VERSION}]")


def _default_scripts_dir() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home() / "scripts"
    except Exception:
        return Path.home() / ".hermes" / "scripts"


def _decode(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(value)
