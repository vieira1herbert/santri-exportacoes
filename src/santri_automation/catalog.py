from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


class ExportCatalog:
    COMPANY_KEYS = {"sol", "horus"}

    def __init__(self, seed_path: Path, user_path: Path) -> None:
        self.seed_path = seed_path
        self.user_path = user_path

    def load(self) -> dict[str, Any]:
        source = self.user_path if self.user_path.exists() else self.seed_path
        data = json.loads(source.read_text(encoding="utf-8"))
        seed = json.loads(self.seed_path.read_text(encoding="utf-8"))
        data.setdefault("settings", copy.deepcopy(seed.get("settings", {})))
        repaired = self._repair_text(data)
        self._validate(repaired)
        return copy.deepcopy(repaired)

    def save(self, data: dict[str, Any]) -> None:
        self._validate(data)
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.user_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.user_path)

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        current = data.setdefault("settings", {})
        startup_company = str(
            payload.get("startup_company") or "sol"
        ).strip()
        if startup_company not in data["companies"]:
            startup_company = "sol"
        current.update(
            {
                "startup_company": startup_company,
                "downloads_folder": str(
                    payload.get("downloads_folder")
                    or "%USERPROFILE%\\Downloads"
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
                "keep_activity_log": bool(
                    payload.get("keep_activity_log", True)
                ),
                "show_success_notification": bool(
                    payload.get("show_success_notification", True)
                ),
            }
        )
        self.save(data)
        return copy.deepcopy(current)

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
                    "schedule": str(payload.get("schedule") or "Manual"),
                    "destination": str(
                        payload.get("destination") or current["destination"]
                    ),
                    "filename_prefix": str(
                        payload.get("filename_prefix")
                        or current.get("filename_prefix")
                        or ""
                    ).strip(),
                    "enabled": bool(payload.get("enabled", True)),
                }
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
                "schedule": str(payload.get("schedule") or "Manual").strip(),
                "destination": str(payload.get("destination") or "").strip(),
                "filename_prefix": str(
                    payload.get("filename_prefix") or ""
                ).strip(),
                "outputs": list(payload.get("outputs") or ["Arquivo principal"]),
                "implemented": False,
                "enabled": bool(payload.get("enabled", True)),
                "last_result": "Em configuração",
                "last_run": "Nunca",
            }
            if current:
                current.update(draft)
                saved = current
            else:
                workflows.append(draft)
                saved = draft

        self.save(data)
        return copy.deepcopy(saved)

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
            return {
                key: cls._repair_text(item)
                for key, item in value.items()
            }
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
