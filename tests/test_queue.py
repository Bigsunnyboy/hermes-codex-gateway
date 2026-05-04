from pathlib import Path

from hermes_local_agent_gateway.queue import FileTaskQueue


def test_file_task_queue_enqueue_approve_and_claim(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")

    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "write",
            "prompt": "Fix tests.",
            "approved": False,
        }
    )

    assert queued["status"] == "APPROVAL_REQUIRED"
    assert queued["task_id"].startswith("queued_")

    approved = queue.approve(queued["task_id"])
    assert approved["approved"] is True
    assert approved["status"] == "QUEUED"

    claimed = queue.claim_next()
    assert claimed is not None
    assert claimed["task_id"] == queued["task_id"]
    assert claimed["status"] == "RUNNING"

    queue.complete(queued["task_id"], {"success": True, "artifact_dir": "/tmp/artifact"})
    finished = queue.get(queued["task_id"])
    assert finished["status"] == "DONE"
    assert finished["result"]["success"] is True


def test_file_task_queue_read_task_is_queued_immediately(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")

    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze only.",
        }
    )

    assert queued["status"] == "QUEUED"
    assert queue.claim_next()["task_id"] == queued["task_id"]


def test_file_task_queue_approve_rejects_tasks_not_waiting_for_approval(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze only.",
        }
    )

    try:
        queue.approve(queued["task_id"])
    except ValueError as exc:
        assert "not awaiting approval" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_file_task_queue_can_reject_task_waiting_for_approval(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "write",
            "prompt": "Fix tests.",
        }
    )

    rejected = queue.reject(queued["task_id"], rejected_by="ou_user")

    assert rejected["status"] == "REJECTED"
    assert rejected["approved"] is False
    assert rejected["approval"]["rejected_by"] == "ou_user"
    assert queue.claim_next() is None


def test_file_task_queue_can_mark_running_task_failed(tmp_path: Path) -> None:
    queue = FileTaskQueue(tmp_path / "queue")
    queued = queue.enqueue(
        {
            "repo": "example-repo",
            "mode": "read",
            "prompt": "Analyze only.",
        }
    )
    queue.claim_next()

    failed = queue.fail(queued["task_id"], "RuntimeError: worker crashed")

    assert failed["status"] == "FAILED"
    assert failed["result"]["error"] == "RuntimeError: worker crashed"
