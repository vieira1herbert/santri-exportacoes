from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from ..scheduler import normalize_schedule
from ..windows_driver import SantriAutomationError


@dataclass(frozen=True)
class PreparedExecutionRequest:
    workflows: tuple[dict[str, Any], ...]
    downloads_root: Path
    existing_file_policy: str
    timeout_seconds: int
    uses_temporary_options: bool


class ExecutionRequestPlanner:
    ACTIONS: ClassVar = frozenset({"export", "redirect", "update", "all"})
    TEMPORARY_FIELDS: ClassVar = (
        "destination",
        "filename_prefix",
        "date_range",
        "include_asset_consumption",
    )

    def prepare(
        self,
        catalog: dict[str, Any],
        company_key: str,
        workflow_ids: list[str],
        action: str,
        temporary_options: dict[str, Any] | None = None,
    ) -> PreparedExecutionRequest:
        self._validate_request(workflow_ids, action)
        settings = catalog.get("settings", {})
        selected = self._select_workflows(catalog, company_key, workflow_ids)
        options = temporary_options if isinstance(temporary_options, dict) else {}
        if options:
            self._validate_temporary_destination(catalog, company_key, options)
            selected = tuple(
                self._apply_temporary_options(item, options) for item in selected
            )
        return PreparedExecutionRequest(
            workflows=selected,
            downloads_root=self._downloads_root(settings),
            existing_file_policy=str(settings.get("existing_file_policy") or "block"),
            timeout_seconds=self._timeout_seconds(settings, options),
            uses_temporary_options=bool(options),
        )

    def _validate_request(self, workflow_ids: list[str], action: str) -> None:
        if action not in self.ACTIONS:
            raise SantriAutomationError("Ação inválida.")
        if not workflow_ids:
            raise SantriAutomationError("Selecione ao menos uma exportação.")

    def _select_workflows(
        self,
        catalog: dict[str, Any],
        company_key: str,
        workflow_ids: list[str],
    ) -> tuple[dict[str, Any], ...]:
        requested = set(workflow_ids)
        workflows = catalog["companies"][company_key]["workflows"]
        selected = tuple(dict(item) for item in workflows if item["id"] in requested)
        if len(selected) != len(requested):
            raise SantriAutomationError(
                "Uma das exportações selecionadas não foi encontrada."
            )
        return selected

    def _validate_temporary_destination(
        self,
        catalog: dict[str, Any],
        company_key: str,
        options: dict[str, Any],
    ) -> None:
        destination = str(options.get("destination") or "").strip()
        if not destination:
            return
        company_root = os.path.normcase(
            os.path.abspath(str(catalog["companies"][company_key]["folder"]))
        )
        destination_root = os.path.normcase(os.path.abspath(destination))
        try:
            inside_company = (
                os.path.commonpath([company_root, destination_root]) == company_root
            )
        except ValueError:
            inside_company = False
        if not inside_company:
            raise SantriAutomationError(
                "O destino temporário deve permanecer dentro da pasta da empresa."
            )

    def _apply_temporary_options(
        self,
        workflow: dict[str, Any],
        options: dict[str, Any],
    ) -> dict[str, Any]:
        prepared = dict(workflow)
        for key in self.TEMPORARY_FIELDS:
            if key in options:
                prepared[key] = options[key]
        schedule = normalize_schedule(prepared.get("schedule"))
        schedule["max_attempts"] = self._bounded_integer(
            options.get("max_attempts") or schedule.get("max_attempts", 3),
            minimum=1,
            maximum=5,
            label="Limite de tentativas",
        )
        schedule.setdefault("priority", 3)
        schedule.setdefault("exceptions", [])
        schedule.setdefault("retry_failed_stage", True)
        prepared["schedule"] = schedule
        return prepared

    @staticmethod
    def _downloads_root(settings: dict[str, Any]) -> Path:
        value = str(settings.get("downloads_folder") or "%USERPROFILE%\\Downloads")
        return Path(os.path.expandvars(value))

    @classmethod
    def _timeout_seconds(
        cls,
        settings: dict[str, Any],
        options: dict[str, Any],
    ) -> int:
        minutes = cls._bounded_integer(
            options.get("timeout_minutes") or settings.get("timeout_minutes") or 10,
            minimum=1,
            maximum=60,
            label="Tempo limite",
        )
        return minutes * 60

    @staticmethod
    def _bounded_integer(
        value: Any,
        *,
        minimum: int,
        maximum: int,
        label: str,
    ) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise SantriAutomationError(f"{label} inválido.") from error
        return max(minimum, min(maximum, number))
