from __future__ import annotations

import json
import fcntl
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from .artifacts import write_json


class FileTaskQueue:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._locked():
            task_id = _new_queue_id()
            risk = payload.get("risk") if isinstance(payload.get("risk"), dict) else {}
            if risk.get("blocked"):
                status = "BLOCKED"
            elif payload.get("mode") == "write" and not payload.get("approved"):
                status = "APPROVAL_REQUIRED"
            else:
                status = "QUEUED"
            record = {
                "task_id": task_id,
                "status": status,
                "approved": bool(payload.get("approved", False)),
                "created_at": _now(),
                "updated_at": _now(),
                "payload": payload,
            }
            self._write(record)
            return record

    def get(self, task_id: str) -> dict[str, Any]:
        path = self._path(task_id)
        if not path.exists():
            raise KeyError(task_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def list_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("queued_*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return records

    def approve(self, task_id: str, approved_by: str | None = None) -> dict[str, Any]:
        with self._locked():
            record = self.get(task_id)
            if record.get("status") == "QUEUED" and record.get("approved"):
                return record
            if record.get("status") != "APPROVAL_REQUIRED":
                raise ValueError(f"Task is not awaiting approval: {record.get('status')}")
            record["approved"] = True
            record["payload"]["approved"] = True
            record["approval"] = {
                **(record.get("approval") or {}),
                "approved_at": _now(),
            }
            if approved_by:
                record["approval"]["approved_by"] = approved_by
            record["status"] = "QUEUED"
            record["updated_at"] = _now()
            self._write(record)
            return record

    def reject(self, task_id: str, rejected_by: str | None = None) -> dict[str, Any]:
        with self._locked():
            record = self.get(task_id)
            if record.get("status") != "APPROVAL_REQUIRED":
                raise ValueError(f"Task is not awaiting approval: {record.get('status')}")
            record["approved"] = False
            record["payload"]["approved"] = False
            record["status"] = "REJECTED"
            record["approval"] = {
                **(record.get("approval") or {}),
                "rejected_at": _now(),
            }
            if rejected_by:
                record["approval"]["rejected_by"] = rejected_by
            record["updated_at"] = _now()
            self._write(record)
            return record

    def claim_next(self) -> dict[str, Any] | None:
        with self._locked():
            for path in sorted(self.root.glob("queued_*.json")):
                record = json.loads(path.read_text(encoding="utf-8"))
                if record.get("status") != "QUEUED":
                    continue
                record["status"] = "RUNNING"
                record["updated_at"] = _now()
                self._write(record)
                return record
        return None

    def complete(self, task_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self._locked():
            record = self.get(task_id)
            record["result"] = result
            record["status"] = "DONE" if result.get("success") else "FAILED"
            record["updated_at"] = _now()
            self._write(record)
            return record

    def fail(self, task_id: str, error: str) -> dict[str, Any]:
        return self.complete(task_id, {"success": False, "error": error})

    def mark_delivery(self, task_id: str, delivery_result: dict[str, Any]) -> dict[str, Any]:
        with self._locked():
            record = self.get(task_id)
            record["delivery_result"] = delivery_result
            record["updated_at"] = _now()
            self._write(record)
            return record

    def mark_approval_card(self, task_id: str, card_info: dict[str, Any]) -> dict[str, Any]:
        with self._locked():
            record = self.get(task_id)
            delivery = record.setdefault("payload", {}).setdefault("delivery", {})
            delivery["approval_card"] = card_info
            record["updated_at"] = _now()
            self._write(record)
            return record

    def mark_card_update(self, task_id: str, update_result: dict[str, Any]) -> dict[str, Any]:
        with self._locked():
            record = self.get(task_id)
            updates = record.setdefault("card_updates", [])
            updates.append(update_result)
            record["updated_at"] = _now()
            self._write(record)
            return record

    def _path(self, task_id: str) -> Path:
        if "/" in task_id or "\\" in task_id:
            raise ValueError("Invalid task id.")
        return self.root / f"{task_id}.json"

    def _write(self, record: dict[str, Any]) -> None:
        write_json(self._path(str(record["task_id"])), record)

    @contextmanager
    def _locked(self):
        lock_path = self.root / "queue.lock"
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _new_queue_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"queued_{timestamp}_{uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
