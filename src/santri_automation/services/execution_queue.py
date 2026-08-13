from __future__ import annotations

import copy
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar
from uuid import uuid4

from .workflow_versions import WorkflowVersionStore


class PersistentExecutionQueue:
    TERMINAL: ClassVar = {"completed", "failed", "cancelled"}

    def __init__(self, root: Path) -> None:
        self.path = root / "execution-queue.json"
        self._lock = threading.RLock()
        self._recover_interrupted()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            return {
                "paused": bool(state["paused"]),
                "jobs": copy.deepcopy(state["jobs"]),
                "summary": self._summary(state),
            }

    def enqueue(
        self, company: str, workflow_ids: list[str], action: str, source: str = "manual"
    ) -> list[dict[str, Any]]:
        with self._lock:
            state = self._load()
            created = []
            for workflow_id in workflow_ids:
                job = {
                    "id": uuid4().hex,
                    "company": company,
                    "workflow_id": workflow_id,
                    "action": action,
                    "source": source,
                    "status": "queued",
                    "created_at": self._now(),
                    "started_at": "",
                    "finished_at": "",
                    "cancel_requested": False,
                    "result": {},
                }
                state["jobs"].append(job)
                created.append(copy.deepcopy(job))
            self._save(state)
            return created

    def pause(self) -> dict[str, Any]:
        return self._set_paused(True)

    def resume(self) -> dict[str, Any]:
        return self._set_paused(False)

    def claim(self) -> dict[str, Any] | None:
        with self._lock:
            state = self._load()
            if state["paused"] or any(
                item["status"] == "running" for item in state["jobs"]
            ):
                return None
            job = next(
                (item for item in state["jobs"] if item["status"] == "queued"), None
            )
            if job is None:
                return None
            job["status"] = "running"
            job["started_at"] = self._now()
            self._save(state)
            return copy.deepcopy(job)

    def finish(self, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            job = self._job(state, job_id)
            job["status"] = (
                "cancelled"
                if job.get("cancel_requested")
                else "completed" if result.get("ok") else "failed"
            )
            job["finished_at"] = self._now()
            job["result"] = copy.deepcopy(result)
            self._save(state)
            return copy.deepcopy(job)

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            job = self._job(state, job_id)
            if job["status"] in self.TERMINAL:
                return copy.deepcopy(job)
            job["cancel_requested"] = True
            if job["status"] == "queued":
                job["status"] = "cancelled"
                job["finished_at"] = self._now()
            self._save(state)
            return copy.deepcopy(job)

    def remove(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            job = self._job(state, job_id)
            if job["status"] not in self.TERMINAL:
                raise ValueError(
                    "Cancele ou aguarde a finalização do item antes de removê-lo."
                )
            state["jobs"] = [item for item in state["jobs"] if item["id"] != job_id]
            self._save(state)
            return copy.deepcopy(job)

    def cancellation_requested(self, job_id: str) -> bool:
        with self._lock:
            job = next(
                (item for item in self._load()["jobs"] if item["id"] == job_id), None
            )
            return bool(job and job.get("cancel_requested"))

    def _set_paused(self, value: bool) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            state["paused"] = value
            self._save(state)
            return self.snapshot()

    def _recover_interrupted(self) -> None:
        with self._lock:
            state = self._load()
            changed = False
            for job in state["jobs"]:
                if job.get("status") == "running":
                    job["status"] = "queued"
                    job["started_at"] = ""
                    changed = True
            if changed:
                self._save(state)

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        expected = str(value.pop("sha256", ""))
        if expected and expected != WorkflowVersionStore.mapping_hash(value):
            quarantine = self.path.with_name(
                f"execution-queue-tampered-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            )
            try:
                os.replace(self.path, quarantine)
            except OSError:
                pass
            value = {}
        jobs = value.get("jobs") if isinstance(value.get("jobs"), list) else []
        return {"paused": bool(value.get("paused", False)), "jobs": jobs[-100:]}

    def _save(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        payload = copy.deepcopy(value)
        payload["sha256"] = WorkflowVersionStore.mapping_hash(payload)
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, self.path)

    @staticmethod
    def _job(state: dict[str, Any], job_id: str) -> dict[str, Any]:
        job = next((item for item in state["jobs"] if item["id"] == job_id), None)
        if job is None:
            raise ValueError("Item da fila não encontrado.")
        return job

    @staticmethod
    def _now() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _summary(state: dict[str, Any]) -> dict[str, int]:
        return {
            status: sum(item["status"] == status for item in state["jobs"])
            for status in ("queued", "running", "completed", "failed", "cancelled")
        }
