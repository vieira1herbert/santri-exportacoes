from __future__ import annotations

import copy
import hmac
import json
import os
import re
import shutil
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any
from uuid import uuid4

from .date_ranges import normalize_date_range
from .scheduler import normalize_schedule
from .security import FileIntegrityService, SecurityViolation


def synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapped


class ExportCatalog:
    COMPANY_KEYS = {"sol", "horus"}

    def __init__(
        self,
        seed_path: Path,
        user_path: Path,
        integrity: FileIntegrityService | None = None,
    ) -> None:
        self.seed_path = seed_path
        self.user_path = user_path
        self.integrity = integrity or FileIntegrityService(user_path.parent)
        self._lock = threading.RLock()

    @synchronized
    def load(self) -> dict[str, Any]:
        source = self.user_path if self.user_path.exists() else self.seed_path
        if source == self.user_path:
            try:
                self.integrity.require_file(source, migrate_legacy=True)
            except SecurityViolation:
                self._quarantine_user_catalog()
                if not self._recover_latest_backup():
                    raise
        data = json.loads(source.read_text(encoding="utf-8"))
        seed = json.loads(self.seed_path.read_text(encoding="utf-8"))
        settings = data.setdefault(
            "settings",
            copy.deepcopy(seed.get("settings", {})),
        )
        for key, value in seed.get("settings", {}).items():
            settings.setdefault(key, copy.deepcopy(value))
        for legacy_key in ("density", "accent_color", "reduce_motion"):
            settings.pop(legacy_key, None)
        data.setdefault("history", [])
        data["version"] = max(2, int(data.get("version") or 1))
        self._ensure_history_chain(data)
        self._merge_implemented_workflows(data, seed)
        for company in data.get("companies", {}).values():
            for workflow in company.get("workflows", []):
                workflow.setdefault(
                    "lifecycle",
                    "production" if workflow.get("implemented") else "draft",
                )
        repaired = self._repair_text(data)
        self._validate(repaired)
        return copy.deepcopy(repaired)

    @classmethod
    def _merge_implemented_workflows(
        cls,
        data: dict[str, Any],
        seed: dict[str, Any],
    ) -> None:
        for company_key in cls.COMPANY_KEYS:
            workflows = data["companies"][company_key]["workflows"]
            seeded = seed["companies"][company_key]["workflows"]
            current_by_id = {item["id"]: item for item in workflows}
            for definition in seeded:
                if not definition.get("implemented"):
                    continue
                current = current_by_id.get(definition["id"])
                if current is None:
                    workflows.append(copy.deepcopy(definition))
                    continue
                current["implemented"] = True
                current["outputs"] = copy.deepcopy(definition["outputs"])
                current["path"] = definition["path"]
                destination = str(current.get("destination") or "")
                if not destination or "{" in destination:
                    current["destination"] = definition["destination"]
                if definition.get("date_range") and not current.get("date_range"):
                    current["date_range"] = copy.deepcopy(definition["date_range"])
                if (
                    "include_asset_consumption" in definition
                    and "include_asset_consumption" not in current
                ):
                    current["include_asset_consumption"] = bool(
                        definition["include_asset_consumption"]
                    )
                if current.get("last_result") == "Em configuração":
                    current["last_result"] = "Pronta para validação"

    @synchronized
    def save(self, data: dict[str, Any]) -> None:
        self._validate(data)
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.user_path.with_suffix(".tmp")
        if self.user_path.exists():
            self._create_backup()
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.user_path)
        self.integrity.seal_file(self.user_path)

    @synchronized
    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        current = data.setdefault("settings", {})
        startup_company = str(payload.get("startup_company") or "sol").strip()
        if startup_company not in data["companies"]:
            startup_company = "sol"
        current.update(
            {
                "startup_company": startup_company,
                "downloads_folder": str(
                    payload.get("downloads_folder") or "%USERPROFILE%\\Downloads"
                ).strip(),
                "existing_file_policy": (
                    "block"
                    if payload.get("existing_file_policy") != "replace"
                    else "replace"
                ),
                "timeout_minutes": max(
                    1,
                    min(60, int(payload.get("timeout_minutes") or 10)),
                ),
                "keep_activity_log": bool(payload.get("keep_activity_log", True)),
                "show_success_notification": bool(
                    payload.get("show_success_notification", True)
                ),
                "start_with_windows": bool(payload.get("start_with_windows", True)),
                "theme": ("dark" if payload.get("theme") == "dark" else "light"),
                "history_retention_days": max(
                    30,
                    min(730, int(payload.get("history_retention_days") or 365)),
                ),
                "artifact_retention_days": max(
                    15,
                    min(365, int(payload.get("artifact_retention_days") or 90)),
                ),
            }
        )
        current.pop("density", None)
        current.pop("accent_color", None)
        current.pop("reduce_motion", None)
        self._apply_history_retention(data)
        self.save(data)
        return copy.deepcopy(current)

    @synchronized
    def upsert_workflow(
        self,
        company_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.load()
        company = data["companies"][company_key]
        workflows = company["workflows"]
        workflow_id = str(payload.get("id") or "").strip()
        if not workflow_id:
            workflow_id = self._unique_id(
                str(payload.get("name") or "nova_exportacao"),
                {item["id"] for item in workflows},
            )

        current = next(
            (item for item in workflows if item["id"] == workflow_id),
            None,
        )
        if current and current.get("implemented"):
            current.update(
                {
                    "description": str(
                        payload.get("description")
                        if payload.get("description") is not None
                        else current.get("description") or ""
                    ).strip(),
                    "schedule": normalize_schedule(
                        payload.get("schedule"),
                        strict=True,
                    ),
                    "destination": str(
                        payload.get("destination") or current["destination"]
                    ),
                    "filename_prefix": str(
                        payload.get("filename_prefix")
                        or current.get("filename_prefix")
                        or ""
                    ).strip(),
                    "enabled": bool(payload.get("enabled", True)),
                    "lifecycle": (
                        str(payload.get("lifecycle"))
                        if payload.get("lifecycle") in {"homologation", "production"}
                        else str(current.get("lifecycle") or "production")
                    ),
                }
            )
            if "date_range" in payload:
                current["date_range"] = normalize_date_range(payload.get("date_range"))
            if "include_asset_consumption" in payload:
                current["include_asset_consumption"] = bool(
                    payload.get("include_asset_consumption")
                )
            saved = current
        else:
            draft = {
                "id": workflow_id,
                "name": str(payload.get("name") or "Nova exportação").strip(),
                "description": str(
                    payload.get("description")
                    or "Fluxo aguardando mapeamento no Santri"
                ).strip(),
                "path": str(payload.get("path") or "").strip(),
                "schedule": normalize_schedule(
                    payload.get("schedule"),
                    strict=True,
                ),
                "destination": str(payload.get("destination") or "").strip(),
                "filename_prefix": str(payload.get("filename_prefix") or "").strip(),
                "outputs": list(payload.get("outputs") or ["Arquivo principal"]),
                "implemented": False,
                "enabled": bool(payload.get("enabled", True)),
                "lifecycle": (
                    str(payload.get("lifecycle"))
                    if payload.get("lifecycle") in {"draft", "homologation"}
                    else "draft"
                ),
                "last_result": "Em configuração",
                "last_run": "Nunca",
            }
            if "date_range" in payload:
                draft["date_range"] = normalize_date_range(payload.get("date_range"))
            if "include_asset_consumption" in payload:
                draft["include_asset_consumption"] = bool(
                    payload.get("include_asset_consumption")
                )
            if "date_range" not in payload and current and current.get("date_range"):
                draft["date_range"] = copy.deepcopy(current["date_range"])
            if current:
                current.update(draft)
                saved = current
            else:
                workflows.append(draft)
                saved = draft

        self.save(data)
        return copy.deepcopy(saved)

    @synchronized
    def restore_workflow_snapshot(
        self,
        company_key: str,
        workflow_id: str,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.load()
        workflows = data["companies"][company_key]["workflows"]
        index = next(
            (
                position
                for position, item in enumerate(workflows)
                if item["id"] == workflow_id
            ),
            None,
        )
        if index is None:
            raise ValueError("Exportação não encontrada.")
        restored = copy.deepcopy(snapshot)
        restored["id"] = workflow_id
        restored["schedule"] = normalize_schedule(restored.get("schedule"), strict=True)
        restored["lifecycle"] = (
            restored.get("lifecycle")
            if restored.get("lifecycle") in {"draft", "homologation", "production"}
            else "production" if restored.get("implemented") else "draft"
        )
        workflows[index] = restored
        self.save(data)
        return copy.deepcopy(restored)

    @synchronized
    def mark_result(
        self,
        company_key: str,
        workflow_id: str,
        result: str,
        last_run: str,
    ) -> None:
        data = self.load()
        workflows = data["companies"][company_key]["workflows"]
        workflow = next(item for item in workflows if item["id"] == workflow_id)
        workflow["last_result"] = result
        workflow["last_run"] = last_run
        self.save(data)

    @synchronized
    def delete_draft_workflow(
        self,
        company_key: str,
        workflow_id: str,
    ) -> dict[str, Any]:
        data = self.load()
        workflows = data["companies"][company_key]["workflows"]
        workflow = next(
            (item for item in workflows if item["id"] == workflow_id),
            None,
        )
        if workflow is None:
            raise ValueError("Exportação não encontrada.")
        if workflow.get("implemented"):
            raise ValueError("Apenas exportações em construção podem ser excluídas.")
        workflows.remove(workflow)
        self.save(data)
        return copy.deepcopy(workflow)

    @synchronized
    def replicate_draft_workflow(
        self,
        source_company: str,
        target_company: str,
        workflow_id: str,
    ) -> dict[str, Any]:
        if source_company == target_company:
            raise ValueError("Selecione empresas diferentes para replicar.")
        data = self.load()
        source = next(
            (
                item
                for item in data["companies"][source_company]["workflows"]
                if item["id"] == workflow_id
            ),
            None,
        )
        if source is None:
            raise ValueError("Exportação de origem não encontrada.")
        if source.get("implemented"):
            raise ValueError("A replicação é destinada a exportações em construção.")
        target_workflows = data["companies"][target_company]["workflows"]
        if any(
            item["name"].casefold() == source["name"].casefold()
            for item in target_workflows
        ):
            raise ValueError(
                "Já existe uma exportação com esse nome na empresa de destino."
            )
        clone = copy.deepcopy(source)
        clone["id"] = self._unique_id(
            source["id"],
            {item["id"] for item in target_workflows},
        )
        clone["schedule"] = {"enabled": False, "entries": []}
        clone["filename_prefix"] = "Sol" if target_company == "sol" else "Horus"
        source_folder = str(data["companies"][source_company]["folder"])
        target_folder = str(data["companies"][target_company]["folder"])
        clone["destination"] = str(clone.get("destination") or "").replace(
            source_folder,
            target_folder,
            1,
        )
        clone["implemented"] = False
        clone["enabled"] = True
        clone["last_result"] = "Em configuração"
        clone["last_run"] = "Nunca"
        clone["replicated_from"] = {
            "company": source_company,
            "workflow_id": workflow_id,
        }
        clone.pop("last_scheduled_slot", None)
        target_workflows.append(clone)
        self.save(data)
        return copy.deepcopy(clone)

    @synchronized
    def mark_scheduled_slot(
        self,
        company_key: str,
        workflow_id: str,
        slot: str,
    ) -> None:
        data = self.load()
        workflows = data["companies"][company_key]["workflows"]
        workflow = next(item for item in workflows if item["id"] == workflow_id)
        workflow["last_scheduled_slot"] = slot
        self.save(data)

    @synchronized
    def append_history(self, event: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        history = data.setdefault("history", [])
        saved = {
            "id": uuid4().hex,
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "company": str(event.get("company") or "system"),
            "workflow_id": str(event.get("workflow_id") or ""),
            "workflow_name": str(event.get("workflow_name") or ""),
            "category": str(event.get("category") or "system"),
            "action": str(event.get("action") or "activity"),
            "status": str(event.get("status") or "info"),
            "source": str(event.get("source") or "manual"),
            "message": self._sanitize_history_text(str(event.get("message") or ""))[
                :4000
            ],
            "details": self._sanitize_history_value(
                copy.deepcopy(event.get("details") or {})
            ),
            "previous_hash": str(history[0].get("event_hash") or "") if history else "",
        }
        saved["event_hash"] = self.integrity.sign_mapping(copy.deepcopy(saved))
        history.insert(0, saved)
        self._apply_history_retention(data)
        self.save(data)
        return copy.deepcopy(saved)

    @staticmethod
    def _apply_history_retention(data: dict[str, Any]) -> None:
        days = max(
            30,
            min(
                730, int(data.get("settings", {}).get("history_retention_days") or 365)
            ),
        )
        cutoff = datetime.now().astimezone().timestamp() - days * 86400
        retained: list[dict[str, Any]] = []
        for event in data.get("history", [])[:2000]:
            try:
                timestamp = datetime.fromisoformat(
                    str(event.get("timestamp"))
                ).timestamp()
            except (TypeError, ValueError):
                timestamp = cutoff
            if timestamp >= cutoff:
                retained.append(event)
        data["history_anchor"] = (
            str(retained[-1].get("previous_hash") or "") if retained else ""
        )
        data["history"] = retained

    @synchronized
    def create_manual_backup(self) -> dict[str, Any]:
        source = self.user_path if self.user_path.exists() else self.seed_path
        backup_dir = self.user_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path = backup_dir / f"export_catalog-manual-{stamp}.json"
        shutil.copy2(source, path)
        self.integrity.seal_file(path)
        return self._backup_info(path)

    @synchronized
    def list_backups(self) -> list[dict[str, Any]]:
        backup_dir = self.user_path.parent / "backups"
        if not backup_dir.exists():
            return []
        return [
            self._backup_info(path)
            for path in sorted(
                backup_dir.glob("export_catalog-*.json"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        ]

    @synchronized
    def restore_backup(self, name: str) -> dict[str, Any]:
        safe_name = Path(str(name)).name
        backup_dir = (self.user_path.parent / "backups").resolve()
        path = (backup_dir / safe_name).resolve()
        if path.parent != backup_dir or not path.is_file():
            raise ValueError("Backup não encontrado.")
        self.integrity.require_file(path, migrate_legacy=True)
        data = json.loads(path.read_text(encoding="utf-8"))
        repaired = self._repair_text(data)
        self._validate(repaired)
        if self.user_path.exists():
            self._create_backup()
        self.save(repaired)
        return self._backup_info(path)

    def _create_backup(self) -> None:
        backup_dir = self.user_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = backup_dir / f"export_catalog-{stamp}.json"
        shutil.copy2(self.user_path, backup)
        self.integrity.seal_file(backup)
        backups = sorted(
            backup_dir.glob("export_catalog-*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for expired in backups[20:]:
            expired.unlink()
            self.integrity.sidecar_path(expired).unlink(missing_ok=True)

    def verify_history_chain(self, data: dict[str, Any] | None = None) -> bool:
        current = data if data is not None else self.load()
        expected = str(current.get("history_anchor") or "")
        for event in reversed(current.get("history", [])):
            if str(event.get("previous_hash") or "") != expected:
                return False
            unsigned = {
                key: value for key, value in event.items() if key != "event_hash"
            }
            calculated = self.integrity.sign_mapping(unsigned)
            if not hmac.compare_digest(str(event.get("event_hash") or ""), calculated):
                return False
            expected = calculated
        return True

    def _ensure_history_chain(self, data: dict[str, Any]) -> None:
        history = data.setdefault("history", [])
        if not history:
            data.setdefault("history_anchor", "")
            return
        if all(item.get("event_hash") is not None for item in history):
            if not self.verify_history_chain(data):
                raise SecurityViolation("A cadeia de auditoria foi alterada.")
            return
        previous = ""
        for event in reversed(history):
            event["previous_hash"] = previous
            unsigned = {
                key: value for key, value in event.items() if key != "event_hash"
            }
            event["event_hash"] = self.integrity.sign_mapping(unsigned)
            previous = event["event_hash"]
        data["history_anchor"] = ""

    def _quarantine_user_catalog(self) -> None:
        if not self.user_path.is_file():
            return
        quarantine = self.user_path.parent / "quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        target = quarantine / f"export_catalog-tampered-{stamp}.json"
        shutil.copy2(self.user_path, target)
        sidecar = self.integrity.sidecar_path(self.user_path)
        if sidecar.is_file():
            shutil.copy2(sidecar, self.integrity.sidecar_path(target))

    def _recover_latest_backup(self) -> bool:
        backup_dir = self.user_path.parent / "backups"
        if not backup_dir.is_dir():
            return False
        backups = sorted(
            backup_dir.glob("export_catalog-*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for backup in backups:
            if self.integrity.verify_file(backup) is not True:
                continue
            shutil.copy2(backup, self.user_path)
            self.integrity.seal_file(self.user_path)
            return True
        return False

    def _backup_info(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime)
            .astimezone()
            .isoformat(timespec="seconds"),
            "manual": "-manual-" in path.name,
            "integrity": self.integrity.verify_file(path) is True,
        }

    @classmethod
    def _sanitize_history_value(cls, value: Any, key: str = "") -> Any:
        if any(
            marker in key.casefold()
            for marker in ("password", "senha", "secret", "token", "credential")
        ):
            return "[PROTEGIDO]"
        if isinstance(value, dict):
            return {
                str(item_key): cls._sanitize_history_value(item, str(item_key))
                for item_key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._sanitize_history_value(item, key) for item in value]
        if isinstance(value, str):
            return cls._sanitize_history_text(value)[:4000]
        if isinstance(value, (bool, int, float)) or value is None:
            return value
        return str(value)[:4000]

    @staticmethod
    def _sanitize_history_text(value: str) -> str:
        return re.sub(
            r"(?i)\b(password|senha|secret|token|credential)\s*[:=]\s*\S+",
            r"\1=[PROTEGIDO]",
            value,
        )

    @staticmethod
    def _unique_id(name: str, existing: set[str]) -> str:
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        base = base or "nova_exportacao"
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    @classmethod
    def _repair_text(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls._repair_text(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._repair_text(item) for item in value]
        if isinstance(value, str) and any(
            marker in value for marker in ("Ã", "Â", "â")
        ):
            try:
                return value.encode("latin-1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                return value
        return value

    @classmethod
    def _validate(cls, data: Any) -> None:
        if not isinstance(data, dict):
            raise ValueError("Catálogo inválido.")
        companies = data.get("companies")
        if not isinstance(companies, dict) or set(companies) != cls.COMPANY_KEYS:
            raise ValueError("Empresas inválidas no catálogo.")
        if not isinstance(data.get("settings"), dict):
            raise ValueError("Configurações inválidas no catálogo.")
        if not isinstance(data.get("history", []), list):
            raise ValueError("Histórico inválido no catálogo.")
        for company in companies.values():
            workflows = company.get("workflows")
            if not isinstance(workflows, list):
                raise ValueError("Lista de exportações inválida.")
            for workflow in workflows:
                if not isinstance(workflow, dict):
                    raise ValueError("Exportação inválida.")
                if not isinstance(workflow.get("id"), str):
                    raise ValueError("Identificador de exportação inválido.")
                if not isinstance(workflow.get("outputs"), list):
                    raise ValueError("Saídas da exportação inválidas.")
                if "date_range" in workflow:
                    normalize_date_range(workflow["date_range"])
                if "include_asset_consumption" in workflow and not isinstance(
                    workflow["include_asset_consumption"], bool
                ):
                    raise ValueError("Configuração de filtros inválida.")
