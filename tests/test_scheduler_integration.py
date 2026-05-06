import json
import subprocess
from pathlib import Path

from hermes_agent_gateway.queue import FileTaskQueue
from hermes_agent_gateway.scheduler import (
    ensure_worker_cron_job,
    ensure_worker_wake_script,
    run_next_queue_task,
)


class FakeRunner:
    def run(
        self,
        *,
        project_path: Path,
        prompt: str,
        mode: str,
        stdout_path: Path,
        stderr_path: Path,
        agent_session_id: str | None = None,
    ):
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return {
            "command": ["codex", "exec", "--cd", str(project_path)],
            "returncode": 0,
            "duration_seconds": 0.01,
        }


class WritingRunner:
    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.calls = []

    def run(
        self,
        *,
        project_path: Path,
        prompt: str,
        mode: str,
        stdout_path: Path,
        stderr_path: Path,
        agent_session_id: str | None = None,
    ):
        self.calls.append(
            {
                "project_path": project_path,
                "prompt": prompt,
                "mode": mode,
                "agent_session_id": agent_session_id,
            }
        )
        assert mode == "write"
        assert project_path != self.repo.resolve()
        assert "worktrees" in project_path.parts
        (project_path / "generated.txt").write_text("generated\n", encoding="utf-8")
        stdout_path.write_text(
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": "Generated file and verified it."},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        stderr_path.write_text("", encoding="utf-8")
        return {
            "command": ["codex", "exec", "--cd", str(project_path)],
            "returncode": 0,
            "duration_seconds": 0.01,
            "agent_session_id": "write-session-1",
        }


class WritingUnexpectedFileRunner:
    def run(
        self,
        *,
        project_path: Path,
        prompt: str,
        mode: str,
        stdout_path: Path,
        stderr_path: Path,
        agent_session_id: str | None = None,
    ):
        assert mode == "write"
        (project_path / "generated.txt").write_text("generated\n", encoding="utf-8")
        (project_path / ".gitignore").write_text(".omx/\n", encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return {
            "command": ["codex", "exec", "--cd", str(project_path)],
            "returncode": 0,
            "duration_seconds": 0.01,
        }


def _init_git_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")


def _commit_file(repo: Path, name: str = "tracked.txt", content: str = "initial\n") -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"add {name}")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def test_run_next_queue_task_claims_and_completes_next_record(tmp_path: Path, gateway_config) -> None:
    repo = tmp_path / "projects" / "example-repo"
    repo.mkdir(parents=True)
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue({"runner": "codex", "repo": "example-repo", "mode": "read", "prompt": "Analyze."})

    result = run_next_queue_task(gateway_config, queue=queue, runner=FakeRunner())

    assert result["task_id"] == queued["task_id"]
    assert result["status"] == "DONE"
    assert result["result"]["success"] is True
    assert queue.get(queued["task_id"])["status"] == "DONE"


def test_run_next_queue_task_delivers_feishu_result_when_target_exists(
    tmp_path: Path, gateway_config
) -> None:
    repo = tmp_path / "projects" / "example-repo"
    repo.mkdir(parents=True)
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "runner": "codex",
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze.",
            "delivery": {
                "platform": "feishu",
                "chat_id": "oc_123",
                "reply_to": "om_msg",
            },
        }
    )
    sends = []

    def fake_sender(**kwargs):
        sends.append(kwargs)
        return {"success": True}

    result = run_next_queue_task(
        gateway_config,
        queue=queue,
        runner=FakeRunner(),
        delivery_sender=fake_sender,
    )

    assert result["task_id"] == queued["task_id"]
    assert result["status"] == "DONE"
    assert result["delivery_result"]["status"] == "DELIVERED"
    assert sends[0]["platform"] == "feishu"
    assert sends[0]["chat_id"] == "oc_123"
    assert queue.get(queued["task_id"])["delivery_result"]["status"] == "DELIVERED"


def test_run_next_queue_task_updates_saved_card_to_running_and_done(
    tmp_path: Path, gateway_config
) -> None:
    repo = tmp_path / "projects" / "example-repo"
    repo.mkdir(parents=True)
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "runner": "codex",
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze.",
            "delivery": {
                "platform": "feishu",
                "chat_id": "oc_123",
                "approval_card": {
                    "platform": "feishu",
                    "chat_id": "oc_123",
                    "message_id": "om_card",
                },
            },
        }
    )
    updates = []

    def fake_card_update(**kwargs):
        updates.append(kwargs)
        return {"success": True, "message_id": kwargs["message_id"]}

    result = run_next_queue_task(
        gateway_config,
        queue=queue,
        runner=FakeRunner(),
        card_updater=fake_card_update,
    )

    assert result["task_id"] == queued["task_id"]
    assert result["status"] == "DONE"
    assert result["delivery_result"]["method"] == "card_update"
    assert [call["card"]["header"]["title"]["content"] for call in updates] == [
        "Agent task running",
        "Agent task done",
    ]
    assert len(queue.get(queued["task_id"])["card_updates"]) == 2


def test_approved_write_queue_task_runs_in_worktree_with_verify_and_keeps_main_repo_clean(
    tmp_path: Path, gateway_config
) -> None:
    repo = tmp_path / "projects" / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    _commit_file(repo)
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "runner": "codex",
            "repo": "example-repo",
            "mode": "write",
            "workspace_id": "write-smoke",
            "prompt": "Create generated.txt.",
            "verify_commands": ["test -f generated.txt"],
        }
    )
    runner = WritingRunner(repo)

    before_approval = run_next_queue_task(gateway_config, queue=queue, runner=runner)

    assert before_approval == {"status": "EMPTY"}
    assert queue.get(queued["task_id"])["status"] == "APPROVAL_REQUIRED"
    assert runner.calls == []

    queue.approve(queued["task_id"])
    result = run_next_queue_task(gateway_config, queue=queue, runner=runner)

    assert result["task_id"] == queued["task_id"]
    assert result["status"] == "DONE"
    assert result["result"]["success"] is True
    assert result["result"]["mode"] == "write"
    assert result["result"]["workspace_changed"] is True
    assert result["result"]["workspace_id"] == "write-smoke"
    assert result["result"]["execution_path"] != result["result"]["project_path"]
    assert result["result"]["verify_results"][0]["command"] == "test -f generated.txt"
    assert result["result"]["verify_results"][0]["returncode"] == 0
    assert len(runner.calls) == 1

    execution_path = Path(result["result"]["execution_path"])
    artifact_dir = Path(result["result"]["artifact_dir"])
    assert (execution_path / "generated.txt").read_text(encoding="utf-8") == "generated\n"
    assert not (repo / "generated.txt").exists()
    assert (artifact_dir / "verify_results.json").exists()
    assert "generated.txt" in (artifact_dir / "after_status.txt").read_text(encoding="utf-8")
    assert (artifact_dir / "agent_stdout.jsonl").exists()
    assert _git(repo, "status", "--short").stdout == ""


def test_approved_write_queue_task_fails_on_changes_outside_allowlist(
    tmp_path: Path, gateway_config
) -> None:
    repo = tmp_path / "projects" / "example-repo"
    repo.mkdir(parents=True)
    _init_git_repo(repo)
    _commit_file(repo)
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "runner": "codex",
            "repo": "example-repo",
            "mode": "write",
            "workspace_id": "write-smoke",
            "prompt": "Create generated.txt.",
            "verify_commands": ["test -f generated.txt"],
            "allowed_paths": ["generated.txt"],
        }
    )

    queue.approve(queued["task_id"])
    result = run_next_queue_task(
        gateway_config,
        queue=queue,
        runner=WritingUnexpectedFileRunner(),
    )

    assert result["status"] == "FAILED"
    assert result["result"]["success"] is False
    assert result["result"]["verify_results"][0]["returncode"] == 0
    assert "Unexpected write changes outside allowlist" in result["result"]["error"]
    assert ".gitignore" in result["result"]["error"]
    assert "generated.txt" not in result["result"]["error"]
    assert _git(repo, "status", "--short").stdout == ""


def test_ensure_worker_cron_job_creates_real_cron_prompt_when_missing(tmp_path: Path) -> None:
    from hermes_agent_gateway.scheduler import WORKER_PROMPT_VERSION

    calls = []

    def fake_cron(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "list":
            return json.dumps({"success": True, "jobs": []})
        return json.dumps({"success": True, "job_id": "job-1", "job": kwargs})

    result = ensure_worker_cron_job(
        cron_api=fake_cron,
        name="agent-queue-worker",
        schedule="every 1m",
        scripts_dir=tmp_path / "scripts",
    )

    assert result["created"] is True
    assert result["job_id"] == "job-1"
    create_call = calls[1]
    assert create_call["action"] == "create"
    assert create_call["name"] == "agent-queue-worker"
    assert create_call["schedule"] == "every 1m"
    assert create_call["enabled_toolsets"] == ["hermes_agent_gateway"]
    assert create_call["script"] == "agent_queue_worker_wake.py"
    assert create_call["prompt"].startswith(f"[{WORKER_PROMPT_VERSION}]")
    assert "run_next_agent_task" in create_call["prompt"]
    assert "final result" in create_call["prompt"]


def test_ensure_worker_cron_job_reuses_existing_job_by_name(tmp_path: Path) -> None:
    calls = []

    def fake_cron(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "list":
            return json.dumps(
                {
                    "success": True,
                    "jobs": [{"id": "job-existing", "name": "agent-queue-worker"}],
                }
            )
        assert kwargs["action"] == "update"
        return json.dumps({"success": True, "job": kwargs})

    result = ensure_worker_cron_job(
        cron_api=fake_cron,
        name="agent-queue-worker",
        schedule="every 1m",
        scripts_dir=tmp_path / "scripts",
    )

    assert result == {
        "created": False,
        "updated": True,
        "job_id": "job-existing",
        "name": "agent-queue-worker",
    }
    assert calls[1]["script"] == "agent_queue_worker_wake.py"


def test_ensure_worker_cron_job_reuses_formatted_cron_listing(tmp_path: Path) -> None:
    from hermes_agent_gateway.scheduler import DEFAULT_WORKER_PROMPT, WORKER_PROMPT_VERSION

    calls = []
    prompt_preview = DEFAULT_WORKER_PROMPT[:100] + "..."
    assert prompt_preview.startswith(f"[{WORKER_PROMPT_VERSION}]")

    def fake_cron(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "list":
            return json.dumps(
                {
                    "success": True,
                    "jobs": [
                        {
                            "job_id": "job-existing",
                            "name": "agent-queue-worker",
                            "prompt_preview": prompt_preview,
                            "script": "agent_queue_worker_wake.py",
                            "enabled_toolsets": ["hermes_agent_gateway"],
                        }
                    ],
                }
            )
        raise AssertionError(f"unexpected cron action: {kwargs}")

    result = ensure_worker_cron_job(
        cron_api=fake_cron,
        name="agent-queue-worker",
        schedule="every 1m",
        scripts_dir=tmp_path / "scripts",
    )

    assert result == {
        "created": False,
        "updated": False,
        "job_id": "job-existing",
        "name": "agent-queue-worker",
    }
    assert len(calls) == 1


def test_ensure_worker_cron_job_updates_stale_prompt_version_preview(tmp_path: Path) -> None:
    calls = []

    def fake_cron(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "list":
            return json.dumps(
                {
                    "success": True,
                    "jobs": [
                        {
                            "job_id": "job-existing",
                            "name": "agent-queue-worker",
                            "prompt_preview": "[gateway-worker-prompt:oldhash]\nUse the Hermes tool...",
                            "script": "agent_queue_worker_wake.py",
                            "enabled_toolsets": ["hermes_agent_gateway"],
                        }
                    ],
                }
            )
        assert kwargs["action"] == "update"
        return json.dumps({"success": True, "job": kwargs})

    result = ensure_worker_cron_job(
        cron_api=fake_cron,
        name="agent-queue-worker",
        schedule="every 1m",
        scripts_dir=tmp_path / "scripts",
    )

    assert result["updated"] is True
    assert calls[1]["prompt"].startswith("[gateway-worker-prompt:")


def test_ensure_worker_cron_job_updates_stale_prompt(tmp_path: Path) -> None:
    calls = []

    def fake_cron(**kwargs):
        calls.append(kwargs)
        if kwargs["action"] == "list":
            return json.dumps(
                {
                    "success": True,
                    "jobs": [
                        {
                            "id": "job-existing",
                            "name": "agent-queue-worker",
                            "prompt": "Use run_next_agent_task once.",
                            "script": "agent_queue_worker_wake.py",
                            "enabled_toolsets": ["hermes_agent_gateway"],
                        }
                    ],
                }
            )
        assert kwargs["action"] == "update"
        return json.dumps({"success": True, "job": kwargs})

    result = ensure_worker_cron_job(
        cron_api=fake_cron,
        name="agent-queue-worker",
        schedule="every 1m",
        scripts_dir=tmp_path / "scripts",
    )

    assert result["updated"] is True
    assert calls[1]["prompt"]
    assert "auto-delivers the final result" in calls[1]["prompt"]


def test_ensure_worker_wake_script_writes_queue_gate(tmp_path: Path) -> None:
    script = ensure_worker_wake_script(tmp_path / "scripts")

    assert script.name == "agent_queue_worker_wake.py"
    content = script.read_text(encoding="utf-8")
    assert "wakeAgent" in content
    assert "QUEUED" in content
    assert "agent_queue" in content
