from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class WorkflowVersionStore:
    def __init__(self, root: Path) -> None:
        self.root = root / "workflow-versions"
        self._lock = threading.RLock()

    def capture(
        self, company: str, workflow: dict[str, Any], reason: str
    ) -> dict[str, Any]:
        with self._lock:
            folder = (
                self.root
                / self.safe(company)
                / self.safe(str(workflow.get("id") or "workflow"))
            )
            folder.mkdir(parents=True, exist_ok=True)
            identifier = (
                f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{uuid4().hex[:6]}"
            )
            payload = {
                "id": identifier,
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "reason": str(reason),
                "company": company,
                "workflow": copy.deepcopy(workflow),
            }
            payload["sha256"] = self.mapping_hash(payload)
            self._write(folder / f"{identifier}.json", payload)
            for obsolete in sorted(folder.glob("*.json"), reverse=True)[20:]:
                obsolete.unlink(missing_ok=True)
            return self._summary(payload)

    def list(self, company: str, workflow_id: str) -> list[dict[str, Any]]:
        folder = self.root / self.safe(company) / self.safe(workflow_id)
        if not folder.exists():
            return []
        values = []
        for path in sorted(folder.glob("*.json"), reverse=True):
            value = self._read(path)
            if value and value.get("sha256") == self.mapping_hash(
                {key: item for key, item in value.items() if key != "sha256"}
            ):
                values.append(self._summary(value))
        return values

    def load(self, company: str, workflow_id: str, version_id: str) -> dict[str, Any]:
        path = (
            self.root
            / self.safe(company)
            / self.safe(workflow_id)
            / f"{self.safe(version_id)}.json"
        )
        value = self._read(path)
        if not value or value.get("sha256") != self.mapping_hash(
            {key: item for key, item in value.items() if key != "sha256"}
        ):
            raise ValueError("Versão de configuração inválida ou adulterada.")
        return copy.deepcopy(value["workflow"])

    @staticmethod
    def mapping_hash(value: dict[str, Any]) -> str:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def safe(value: str) -> str:
        safe = "".join(
            character
            for character in value
            if character.isalnum() or character in {"-", "_"}
        )
        if not safe:
            raise ValueError("Identificador inválido.")
        return safe

    @staticmethod
    def _summary(value: dict[str, Any]) -> dict[str, Any]:
        workflow = value.get("workflow", {})
        return {
            "id": value.get("id"),
            "timestamp": value.get("timestamp"),
            "reason": value.get("reason"),
            "sha256": value.get("sha256"),
            "name": workflow.get("name"),
            "lifecycle": workflow.get(
                "lifecycle", "production" if workflow.get("implemented") else "draft"
            ),
        }

    @staticmethod
    def _read(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _write(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
