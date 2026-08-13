from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, ClassVar

from ..domain import WorkflowBlueprintRegistry


class WorkflowSimulator:
    ACTIONS: ClassVar = {"export", "redirect", "update", "all"}

    def __init__(self, registry: WorkflowBlueprintRegistry) -> None:
        self.registry = registry

    def simulate(
        self,
        catalog: dict[str, Any],
        company_key: str,
        workflow_id: str,
        action: str = "all",
    ) -> dict[str, Any]:
        company = catalog.get("companies", {}).get(company_key)
        if not isinstance(company, dict):
            return self._result("Empresa não encontrada.")
        workflow = next(
            (
                item
                for item in company.get("workflows", [])
                if item.get("id") == workflow_id
            ),
            None,
        )
        if not isinstance(workflow, dict):
            return self._result("Exportação não encontrada.")
        blueprint = self.registry.get(workflow_id)
        checks: list[dict[str, Any]] = []
        self._check(
            checks,
            "executor",
            blueprint is not None,
            "Executor modular registrado",
            "Executor Windows ainda não implementado",
        )
        self._check(
            checks, "action", action in self.ACTIONS, "Ação suportada", "Ação inválida"
        )
        self._check(
            checks,
            "implemented",
            bool(workflow.get("implemented")),
            "Automação implementada",
            "Automação ainda está em construção",
        )
        self._check(
            checks,
            "enabled",
            bool(workflow.get("enabled", True)),
            "Exportação habilitada",
            "Exportação desabilitada",
        )
        destination = str(workflow.get("destination") or "").strip()
        self._check(
            checks,
            "destination",
            action not in {"redirect", "update", "all"} or bool(destination),
            "Destino configurado",
            "Destino obrigatório não configurado",
        )
        if destination:
            company_root = os.path.normcase(
                os.path.abspath(str(company.get("folder") or ""))
            )
            target = os.path.normcase(os.path.abspath(destination))
            try:
                inside = os.path.commonpath([company_root, target]) == company_root
            except ValueError:
                inside = False
            self._check(
                checks,
                "destination_scope",
                inside,
                "Destino dentro da pasta corporativa",
                "Destino fora da pasta autorizada da empresa",
            )
        self._check(
            checks,
            "filename_prefix",
            bool(str(workflow.get("filename_prefix") or "").strip()),
            "Prefixo de arquivo configurado",
            "Prefixo de arquivo não configurado",
        )
        downloads = os.path.expandvars(
            str(
                catalog.get("settings", {}).get("downloads_folder")
                or "%USERPROFILE%\\Downloads"
            )
        )
        self._check(
            checks,
            "downloads",
            bool(downloads),
            "Pasta temporária definida",
            "Pasta temporária não definida",
        )
        ready = all(item["status"] == "ok" for item in checks)
        stages = (
            []
            if blueprint is None
            else [
                {**asdict(stage), "selected": action == "all" or action == stage.key}
                for stage in blueprint.stages
            ]
        )
        return {
            "ok": True,
            "ready": ready,
            "company": company_key,
            "workflow_id": workflow_id,
            "workflow_name": str(workflow.get("name") or workflow_id),
            "action": action,
            "lifecycle": str(
                workflow.get("lifecycle")
                or ("production" if workflow.get("implemented") else "draft")
            ),
            "checks": checks,
            "stages": stages,
            "message": (
                "Simulação aprovada sem interagir com o Santri."
                if ready
                else "A simulação encontrou configurações que precisam de correção."
            ),
        }

    @staticmethod
    def _check(
        checks: list[dict[str, Any]], key: str, valid: bool, success: str, failure: str
    ) -> None:
        checks.append(
            {
                "key": key,
                "status": "ok" if valid else "error",
                "message": success if valid else failure,
            }
        )

    @staticmethod
    def _result(message: str) -> dict[str, Any]:
        return {
            "ok": False,
            "ready": False,
            "message": message,
            "checks": [],
            "stages": [],
        }
