from __future__ import annotations

import csv
import ctypes
import hashlib
import json
import os
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

import webview

from . import __version__
from .catalog import ExportCatalog
from .config import load_config
from .executors import ExecutionContext, ExecutorRegistry, build_default_registry
from .platform import (
    PersistentExecutionQueue,
    WorkflowSimulator,
    WorkflowVersionStore,
    build_blueprint_registry,
)
from .reliability import ReliabilityCenter
from .resource_paths import resource_path
from .scheduler import WorkflowScheduler, normalize_schedule
from .security import WindowsSecurityService
from .services.operational_monitoring import OperationalMonitoring
from .services.release_manager import ReleaseManager
from .services.schedule_center import ScheduleCenter
from .services.system_diagnostics import SystemDiagnostics
from .single_instance import SingleInstance
from .startup import configure_startup
from .windows_driver import SantriAutomationError, WindowsSantriDriver


def _automation_config_path() -> Path:
    return resource_path("config", "cadastro_produtos.json")


def _catalog_seed_path() -> Path:
    return resource_path("config", "export_catalog.json")


def _dashboard_path() -> Path:
    return resource_path("ui", "dashboard.html")


def _user_catalog_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    app_root = root / "Santri Export"
    preferences = app_root / "release-management" / "preferences.json"
    environment = "production"
    try:
        value = json.loads(preferences.read_text(encoding="utf-8"))
        if value.get("environment") == "homologation":
            environment = "homologation"
    except (OSError, json.JSONDecodeError):
        pass
    return app_root / (
        "export_catalog.json"
        if environment == "production"
        else "homologation/export_catalog.json"
    )


class DashboardApi:
    REPOSITORY_URL = "https://github.com/vieira1herbert/santri-exportacoes"

    def __init__(
        self,
        catalog: ExportCatalog | None = None,
        driver_factory: Any = None,
        config_loader: Any = None,
        executor_registry: ExecutorRegistry | None = None,
        preflight_validator: Any = None,
    ) -> None:
        self.window: webview.Window | None = None
        self.catalog = catalog or ExportCatalog(
            _catalog_seed_path(), _user_catalog_path()
        )
        if not self.catalog.user_path.exists():
            self.catalog.save(self.catalog.load())
        self._driver_factory = driver_factory
        self._config_loader = config_loader
        self._executors = executor_registry or build_default_registry()
        self._preflight_validator = preflight_validator
        self._execution_lock = threading.Lock()
        self._queue_wake = threading.Event()
        self._queue_thread: threading.Thread | None = None
        self._retention_days: int | None = None
        self._maintenance = {
            "reports": 0,
            "checkpoints": 0,
            "evidence": 0,
            "support": 0,
        }
        self.security = WindowsSecurityService(
            self.catalog.user_path.parent,
            self.catalog.integrity,
        )
        self.reliability = ReliabilityCenter(
            self.catalog.user_path.parent,
            self.catalog.integrity,
        )
        self.diagnostics = SystemDiagnostics(
            self.catalog,
            _automation_config_path(),
            config_loader,
        )
        self.monitoring = OperationalMonitoring()
        self.schedule_center = ScheduleCenter()
        self.blueprints = build_blueprint_registry()
        self.simulator = WorkflowSimulator(self.blueprints)
        self.workflow_versions = WorkflowVersionStore(self.catalog.user_path.parent)
        self.execution_queue = PersistentExecutionQueue(self.catalog.user_path.parent)
        release_root = self.catalog.user_path.parent
        if release_root.name == "homologation":
            release_root = release_root.parent
        self.release_manager = ReleaseManager(
            release_root,
            __version__,
            resource_path("config", "CHANGELOG.md"),
        )
        self.scheduler = WorkflowScheduler(
            self.catalog,
            self._run_scheduled_workflow,
            on_error=self._record_scheduler_error,
        )

    def get_state(self) -> dict[str, Any]:
        state = self.catalog.load()
        health = self._system_health(state)
        security = self.security.status(
            self.catalog.user_path,
            self.catalog.verify_history_chain(state),
        )
        retention = self._retention_state(state.get("settings", {}))
        reports = self.reliability.latest_reports(limit=500)
        monitoring = self.monitoring.snapshot(
            state,
            reports,
            health,
            security,
        )
        scheduling = self.schedule_center.snapshot(state, reports)
        queue = self.execution_queue.snapshot()
        notifications = self.reliability.notifications.list()
        state["application"] = {
            "version": __version__,
            "security": security,
            "health": health,
            "monitoring": monitoring,
            "scheduling": scheduling,
            "release": self.release_manager.status(),
            "platform": {
                "catalog_version": int(state.get("version") or 2),
                "blueprints": self.blueprints.describe(),
                "queue": queue,
                "lifecycle": self._lifecycle_summary(state),
            },
            "maintenance": retention,
            "notifications": notifications,
            "unread_notifications": sum(
                not bool(item.get("read")) for item in notifications
            ),
            "pending_checkpoint": self.reliability.pending_checkpoint(),
            "reports": reports[:20],
            "backups": self.catalog.list_backups(),
        }
        return state

    def _retention_state(self, settings: dict[str, Any]) -> dict[str, int]:
        days = int(settings.get("artifact_retention_days") or 90)
        if self._retention_days != days:
            self._maintenance = self.reliability.apply_retention(days)
            self._retention_days = days
        return dict(self._maintenance)

    def copy_operational_summary(self) -> dict[str, Any]:
        state = self.get_state()
        application = state["application"]
        summary = self.monitoring.technical_summary(
            application["monitoring"],
            application["health"],
            application["security"],
        )
        try:
            import win32clipboard

            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(summary)
            finally:
                win32clipboard.CloseClipboard()
        except Exception as error:
            return {"ok": False, "error": f"Não foi possível copiar: {error}"}
        return {"ok": True, "summary": summary}

    def open_repository(self) -> dict[str, Any]:
        opened = webbrowser.open(self.REPOSITORY_URL, new=2)
        return {"ok": bool(opened), "url": self.REPOSITORY_URL}

    def check_for_updates(self, channel: str = "") -> dict[str, Any]:
        result = self.release_manager.check(channel or None)
        self._append_history(
            company="system",
            category="release",
            action="update_check",
            status="success" if result.get("ok") else "error",
            source="manual",
            message=(
                "Consulta de atualização concluída."
                if result.get("ok")
                else str(result.get("error") or "Falha na consulta.")
            ),
            details={
                "channel": channel or self.release_manager.preferences()["channel"]
            },
        )
        return result

    def save_release_preferences(self, payload: dict[str, Any]) -> dict[str, Any]:
        previous = self.release_manager.preferences()
        saved = self.release_manager.save_preferences(payload)
        self._append_history(
            company="system",
            category="release",
            action="release_preferences",
            status="success",
            source="manual",
            message="Preferências de homologação e atualização alteradas.",
            details={"previous": previous, "current": saved},
        )
        return {
            "ok": True,
            "preferences": saved,
            "restart_required": previous["environment"] != saved["environment"],
        }

    def prepare_update(self, release: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self.release_manager.prepare_update(
                release, self.catalog.user_path
            )
            self._append_history(
                company="system",
                category="release",
                action="update_prepare",
                status="success",
                source="manual",
                message=f"Release {result['version']} verificada e preparada.",
                details={"version": result["version"]},
            )
            return result
        except (OSError, ValueError) as error:
            self._append_history(
                company="system",
                category="release",
                action="update_prepare",
                status="error",
                source="manual",
                message=str(error),
            )
            return {"ok": False, "error": str(error)}

    def rollback_release(self) -> dict[str, Any]:
        result = self.release_manager.rollback_plan()
        self._append_history(
            company="system",
            category="release",
            action="rollback_plan",
            status="success" if result.get("ok") else "error",
            source="manual",
            message=(
                f"Reversão preparada para {result.get('version')}."
                if result.get("ok")
                else str(result.get("error"))
            ),
        )
        return result

    def activate_release(self, version: str) -> dict[str, Any]:
        try:
            result = self.release_manager.activate(version)
            self._append_history(
                company="system",
                category="release",
                action="release_activate",
                status="success",
                source="manual",
                message=f"Release {version} selecionada para a próxima inicialização.",
                details={"version": version},
            )
            return result
        except (OSError, ValueError) as error:
            self._append_history(
                company="system",
                category="release",
                action="release_activate",
                status="error",
                source="manual",
                message=str(error),
            )
            return {"ok": False, "error": str(error)}

    def run_diagnostics(self) -> dict[str, Any]:
        state = self.catalog.load()
        health = self._detailed_health(state)
        level = "success" if health["ready"] else "warning"
        self.reliability.notifications.add(
            level,
            "Diagnóstico concluído",
            (
                "Todos os componentes obrigatórios estão disponíveis."
                if health["ready"]
                else f"{health['failed']} verificação(ões) requerem atenção."
            ),
            {"checks": health["checks"]},
        )
        self._append_history(
            company="system",
            category="diagnostic",
            action="diagnostic_run",
            status="success" if health["ready"] else "blocked",
            source="manual",
            message="Diagnóstico completo do ambiente executado.",
            details=health,
        )
        return {"ok": True, "diagnostic": health}

    def create_support_package(self) -> dict[str, Any]:
        state = self.catalog.load()
        health = self._detailed_health(state)
        path = self.reliability.create_support_package(
            state,
            health,
            self.catalog.user_path.parent / "app-errors.log",
        )
        self.reliability.notifications.add(
            "success",
            "Pacote de suporte criado",
            f"Diagnóstico salvo em {path}",
            {"path": str(path)},
        )
        return {"ok": True, "path": str(path)}

    def create_catalog_backup(self) -> dict[str, Any]:
        backup = self.catalog.create_manual_backup()
        self.reliability.notifications.add(
            "success",
            "Backup criado",
            "As configurações atuais foram protegidas.",
            backup,
        )
        return {"ok": True, "backup": backup}

    def restore_catalog_backup(self, name: str) -> dict[str, Any]:
        backup = self.catalog.restore_backup(name)
        self.reliability.notifications.add(
            "success",
            "Backup restaurado",
            f"As configurações de {name} foram restauradas.",
            backup,
        )
        self._append_history(
            company="system",
            category="configuration",
            action="backup_restored",
            status="success",
            source="manual",
            message=f"Backup de configurações restaurado: {name}.",
        )
        return {"ok": True, "backup": backup}

    def mark_notifications_read(self) -> dict[str, Any]:
        return {"ok": True, "changed": self.reliability.notifications.mark_all_read()}

    def clear_notifications(self) -> dict[str, Any]:
        return {"ok": True, "removed": self.reliability.notifications.clear()}

    def resume_execution(self, execution_id: str) -> dict[str, Any]:
        checkpoint = self.reliability.pending_checkpoint()
        if checkpoint is None or checkpoint.get("id") != execution_id:
            return {"ok": False, "error": "Checkpoint para retomada não encontrado."}
        return self.run_workflows(
            str(checkpoint["company"]),
            [str(value) for value in checkpoint["workflow_ids"]],
            str(checkpoint["action"]),
            source="resume",
            resume_execution_id=execution_id,
        )

    def dismiss_checkpoint(self, execution_id: str) -> dict[str, Any]:
        dismissed = self.reliability.dismiss_checkpoint(execution_id)
        return {
            "ok": dismissed,
            "error": "Checkpoint não encontrado." if not dismissed else "",
        }

    def export_history_csv(self) -> dict[str, Any]:
        state = self.catalog.load()
        downloads = Path(
            os.path.expandvars(
                str(
                    state.get("settings", {}).get("downloads_folder")
                    or "%USERPROFILE%\\Downloads"
                )
            )
        )
        downloads.mkdir(parents=True, exist_ok=True)
        path = downloads / (
            "Santri-Historico-" f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
        )
        fields = (
            "timestamp",
            "company",
            "source",
            "category",
            "action",
            "workflow_name",
            "status",
            "message",
            "details",
        )
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
            writer.writeheader()
            for event in state.get("history", []):
                writer.writerow(
                    {
                        field: (
                            json.dumps(event.get(field), ensure_ascii=False)
                            if field == "details"
                            else event.get(field, "")
                        )
                        for field in fields
                    }
                )
        self._append_history(
            company="system",
            category="audit",
            action="history_exported",
            status="success",
            source="manual",
            message="Histórico exportado para CSV.",
            details={"path": str(path)},
        )
        return {"ok": True, "path": str(path)}

    def save_workflow(
        self,
        company_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_company(company_key)
        workflows = self.catalog.load()["companies"][company_key]["workflows"]
        workflow_id = str(payload.get("id") or "")
        existed = any(item["id"] == workflow_id for item in workflows)
        previous = next(
            (dict(item) for item in workflows if item["id"] == workflow_id), None
        )
        if previous:
            self.workflow_versions.capture(company_key, previous, "Antes da alteração")
        saved = self.catalog.upsert_workflow(company_key, payload)
        self.workflow_versions.capture(company_key, saved, "Configuração salva")
        self._append_history(
            company=company_key,
            workflow_id=saved["id"],
            workflow_name=saved["name"],
            category="configuration",
            action="workflow_updated" if existed else "workflow_created",
            status="success",
            source="manual",
            message=(
                f"Exportação “{saved['name']}” atualizada."
                if existed
                else f"Exportação “{saved['name']}” criada."
            ),
            details={
                "description": saved.get("description"),
                "path": saved.get("path"),
                "schedule": saved.get("schedule"),
                "destination": saved.get("destination"),
                "filename_prefix": saved.get("filename_prefix"),
                "date_range": saved.get("date_range"),
                "enabled": saved.get("enabled"),
            },
        )
        return saved

    def simulate_workflow(
        self,
        company_key: str,
        workflow_id: str,
        action: str = "all",
    ) -> dict[str, Any]:
        self._validate_company(company_key)
        result = self.simulator.simulate(
            self.catalog.load(), company_key, workflow_id, action
        )
        self._append_history(
            company=company_key,
            workflow_id=workflow_id,
            category="homologation",
            action="workflow_simulated",
            status="success" if result.get("ready") else "warning",
            source="manual",
            message=str(result.get("message") or "Simulação concluída."),
            details={"action": action, "checks": result.get("checks", [])},
        )
        return result

    def list_workflow_versions(
        self,
        company_key: str,
        workflow_id: str,
    ) -> list[dict[str, Any]]:
        self._validate_company(company_key)
        return self.workflow_versions.list(company_key, workflow_id)

    def restore_workflow_version(
        self,
        company_key: str,
        workflow_id: str,
        version_id: str,
    ) -> dict[str, Any]:
        self._validate_company(company_key)
        current = next(
            item
            for item in self.catalog.load()["companies"][company_key]["workflows"]
            if item["id"] == workflow_id
        )
        self.workflow_versions.capture(company_key, current, "Antes da restauração")
        snapshot = self.workflow_versions.load(company_key, workflow_id, version_id)
        restored = self.catalog.restore_workflow_snapshot(
            company_key, workflow_id, snapshot
        )
        self.workflow_versions.capture(company_key, restored, "Versão restaurada")
        self._append_history(
            company=company_key,
            workflow_id=workflow_id,
            workflow_name=str(restored.get("name") or workflow_id),
            category="configuration",
            action="workflow_version_restored",
            status="success",
            source="manual",
            message="Versão anterior da configuração restaurada.",
            details={"version_id": version_id},
        )
        return restored

    def enqueue_workflows(
        self,
        company_key: str,
        workflow_ids: list[str],
        action: str = "all",
    ) -> dict[str, Any]:
        self._validate_company(company_key)
        if action not in {"export", "redirect", "update", "all"}:
            raise ValueError("Ação inválida.")
        if not workflow_ids:
            raise ValueError("Selecione ao menos uma exportação.")
        catalog = self.catalog.load()
        simulations = [
            self.simulator.simulate(catalog, company_key, workflow_id, action)
            for workflow_id in workflow_ids
        ]
        blocked = [item for item in simulations if not item.get("ready")]
        if blocked:
            return {
                "ok": False,
                "error": "A fila foi bloqueada pela simulação preventiva.",
                "simulations": simulations,
            }
        jobs = self.execution_queue.enqueue(company_key, workflow_ids, action)
        self._queue_wake.set()
        return {"ok": True, "jobs": jobs, "queue": self.execution_queue.snapshot()}

    def pause_execution_queue(self) -> dict[str, Any]:
        return self.execution_queue.pause()

    def get_execution_queue(self) -> dict[str, Any]:
        return self.execution_queue.snapshot()

    def resume_execution_queue(self) -> dict[str, Any]:
        result = self.execution_queue.resume()
        self._queue_wake.set()
        return result

    def cancel_queue_item(self, job_id: str) -> dict[str, Any]:
        return self.execution_queue.cancel(job_id)

    def remove_queue_item(self, job_id: str) -> dict[str, Any]:
        removed = self.execution_queue.remove(job_id)
        self._append_history(
            company=str(removed.get("company") or "system"),
            category="configuration",
            action="queue_item_removed",
            status="success",
            source="manual",
            workflow_id=str(removed.get("workflow_id") or ""),
            message="Item removido da fila persistente.",
            details={
                "queue_job_id": removed.get("id"),
                "previous_status": removed.get("status"),
            },
        )
        return {
            "ok": True,
            "removed": removed,
            "queue": self.execution_queue.snapshot(),
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        saved = self.catalog.save_settings(payload)
        configure_startup(saved.get("start_with_windows", True))
        self._append_history(
            company="system",
            category="configuration",
            action="settings_updated",
            status="success",
            source="manual",
            message="Configurações gerais atualizadas.",
            details=saved,
        )
        return saved

    def delete_workflow(
        self,
        company_key: str,
        workflow_id: str,
    ) -> dict[str, Any]:
        self._validate_company(company_key)
        deleted = self.catalog.delete_draft_workflow(
            company_key,
            workflow_id,
        )
        self._append_history(
            company=company_key,
            workflow_id=workflow_id,
            workflow_name=deleted["name"],
            category="configuration",
            action="workflow_deleted",
            status="success",
            source="manual",
            message=f"Exportação “{deleted['name']}” excluída.",
        )
        return {
            "ok": True,
            "message": f"Exportação “{deleted['name']}” excluída.",
        }

    def replicate_workflow(
        self,
        source_company: str,
        target_company: str,
        workflow_id: str,
    ) -> dict[str, Any]:
        self._validate_company(source_company)
        self._validate_company(target_company)
        replicated = self.catalog.replicate_draft_workflow(
            source_company,
            target_company,
            workflow_id,
        )
        self._append_history(
            company=target_company,
            workflow_id=replicated["id"],
            workflow_name=replicated["name"],
            category="configuration",
            action="workflow_replicated",
            status="success",
            source="manual",
            message=(
                f"Exportação “{replicated['name']}” replicada de "
                f"{source_company.upper()} para {target_company.upper()}."
            ),
            details={"source_company": source_company},
        )
        return {
            "ok": True,
            "message": (f"Exportação replicada para {target_company.upper()}."),
        }

    def start_scheduler(self) -> None:
        self.scheduler.start()
        if self._queue_thread is None or not self._queue_thread.is_alive():
            self._queue_thread = threading.Thread(
                target=self._queue_loop,
                name="SantriExecutionQueue",
                daemon=True,
            )
            self._queue_thread.start()

    def _run_scheduled_workflow(
        self,
        company_key: str,
        workflow_id: str,
    ) -> dict[str, Any]:
        self._emit_progress("Agendamento iniciado automaticamente.")
        result = self.run_workflows(
            company_key,
            [workflow_id],
            "all",
            source="schedule",
        )
        if (
            not result.get("ok")
            and "em andamento" not in str(result.get("error") or "").lower()
        ):
            self.catalog.mark_result(
                company_key,
                workflow_id,
                "Falha no agendamento",
                datetime.now().strftime("%d/%m · %H:%M"),
            )
        return result

    def run_workflows(
        self,
        company_key: str,
        workflow_ids: list[str],
        action: str,
        source: str = "manual",
        resume_execution_id: str = "",
        temporary_options: dict[str, Any] | None = None,
        queue_job_id: str = "",
    ) -> dict[str, Any]:
        if not self._execution_lock.acquire(blocking=False):
            self._append_history(
                company=company_key,
                category="execution",
                action=action,
                status="blocked",
                source=source,
                message="Execução bloqueada: outra operação estava em andamento.",
            )
            return {
                "ok": False,
                "error": "Já existe uma operação em andamento.",
            }
        current_workflow: dict[str, Any] | None = None
        session = None
        try:
            self._validate_company(company_key)
            if action not in {"export", "redirect", "update", "all"}:
                raise SantriAutomationError("Ação inválida.")
            if not workflow_ids:
                raise SantriAutomationError("Selecione ao menos uma exportação.")

            catalog = self.catalog.load()
            settings = catalog.get("settings", {})
            downloads_root = Path(
                os.path.expandvars(
                    str(settings.get("downloads_folder") or "%USERPROFILE%\\Downloads")
                )
            )
            existing_file_policy = str(settings.get("existing_file_policy") or "block")
            options = temporary_options if isinstance(temporary_options, dict) else {}
            timeout_seconds = (
                max(
                    1,
                    min(
                        60,
                        int(
                            options.get("timeout_minutes")
                            or settings.get("timeout_minutes")
                            or 10
                        ),
                    ),
                )
                * 60
            )
            workflows = catalog["companies"][company_key]["workflows"]
            selected = [
                dict(workflow)
                for workflow in workflows
                if workflow["id"] in set(workflow_ids)
            ]
            if len(selected) != len(set(workflow_ids)):
                raise SantriAutomationError(
                    "Uma das exportações selecionadas não foi encontrada."
                )
            if options:
                temporary_destination = str(options.get("destination") or "").strip()
                if temporary_destination:
                    company_root = os.path.normcase(
                        os.path.abspath(
                            str(catalog["companies"][company_key]["folder"])
                        )
                    )
                    destination_root = os.path.normcase(
                        os.path.abspath(temporary_destination)
                    )
                    try:
                        inside_company = (
                            os.path.commonpath([company_root, destination_root])
                            == company_root
                        )
                    except ValueError:
                        inside_company = False
                    if not inside_company:
                        raise SantriAutomationError(
                            "O destino temporário deve permanecer dentro da pasta da empresa."
                        )
                for workflow in selected:
                    for key in (
                        "destination",
                        "filename_prefix",
                        "date_range",
                        "include_asset_consumption",
                    ):
                        if key in options:
                            workflow[key] = options[key]
                    schedule = normalize_schedule(workflow.get("schedule"))
                    schedule["max_attempts"] = max(
                        1,
                        min(
                            5,
                            int(
                                options.get("max_attempts")
                                or schedule.get("max_attempts", 3)
                            ),
                        ),
                    )
                    schedule.setdefault("priority", 3)
                    schedule.setdefault("exceptions", [])
                    schedule.setdefault("retry_failed_stage", True)
                    workflow["schedule"] = schedule

            current_workflow = selected[0] if selected else None
            preflight = (
                self._preflight_validator(
                    catalog,
                    company_key,
                    workflow_ids,
                    action,
                )
                if self._preflight_validator
                else self.diagnostics.execution_preflight(
                    catalog,
                    company_key,
                    workflow_ids,
                    action,
                )
            )
            if not preflight["ready"]:
                failures = ", ".join(
                    item["name"]
                    for item in preflight["checks"]
                    if item["required"] and item["status"] != "ok"
                )
                raise SantriAutomationError(
                    f"Diagnóstico preventivo bloqueou a execução: {failures}."
                )

            session = self.reliability.start_session(
                company_key,
                workflow_ids,
                action,
                source,
                execution_id=resume_execution_id or None,
            )

            def progress_message(message: str) -> None:
                session.record("automation", "info", message)
                self._emit_progress(message)

            for workflow in selected:
                self._append_history(
                    company=company_key,
                    workflow_id=workflow["id"],
                    workflow_name=workflow["name"],
                    category="execution",
                    action=action,
                    status="started",
                    source=source,
                    message=(f"Execução de “{workflow['name']}” iniciada."),
                    details={
                        "preflight": preflight,
                        "temporary_parameters": bool(options),
                    },
                )

            config = (self._config_loader or load_config)(_automation_config_path())
            driver = (self._driver_factory or WindowsSantriDriver)(
                config,
                logger=progress_message,
            )
            generated: list[Path] = []

            for workflow in selected:
                current_workflow = workflow
                if not workflow.get("implemented"):
                    raise SantriAutomationError(
                        f"A exportação “{workflow['name']}” ainda está "
                        "em configuração."
                    )

                self._emit_progress(f"Iniciando o fluxo completo: {workflow['name']}.")
                session.record(
                    "workflow",
                    "running",
                    f"Iniciando {workflow['name']}.",
                    {"workflow_id": workflow["id"]},
                )
                prefix = str(workflow.get("filename_prefix") or "").strip()
                destination = str(workflow.get("destination") or "").strip()
                workflow_id = workflow["id"]
                retry_count = max(
                    0,
                    int(
                        normalize_schedule(workflow.get("schedule")).get(
                            "max_attempts", 3
                        )
                    )
                    - 1,
                )
                context = ExecutionContext(
                    company_key=company_key,
                    filename_prefix=prefix,
                    destination=Path(destination) if destination else None,
                    downloads_root=downloads_root,
                    backup_root=self.catalog.user_path.parent / "file-backups",
                    existing_file_policy=existing_file_policy,
                    timeout_seconds=timeout_seconds,
                    date_range=workflow.get("date_range"),
                    include_asset_consumption=bool(
                        workflow.get("include_asset_consumption", False)
                    ),
                    workflow_id=workflow_id,
                    step_runner=lambda name, operation, workflow_id=workflow_id, retry_count=retry_count: self._run_queue_aware_step(
                        queue_job_id, session, workflow_id, name, operation, retry_count
                    ),
                )
                executor = self._executors.get(workflow["id"])
                paths = executor.execute(action, driver, context)
                generated.extend(paths)
                self.catalog.mark_result(
                    company_key,
                    workflow["id"],
                    (
                        "Fluxo completo"
                        if action == "all"
                        else "Base atualizada" if action == "update" else "Concluído"
                    ),
                    datetime.now().strftime("%d/%m · %H:%M"),
                )
                self._append_history(
                    company=company_key,
                    workflow_id=workflow["id"],
                    workflow_name=workflow["name"],
                    category="execution",
                    action=action,
                    status="success",
                    source=source,
                    message=f"Execução de “{workflow['name']}” concluída.",
                    details={
                        "paths": [str(path) for path in paths],
                        "artifacts": self._artifact_evidence(paths),
                    },
                )
                session.record(
                    "workflow",
                    "success",
                    f"Fluxo concluído: {workflow['name']}.",
                    {"workflow_id": workflow["id"]},
                )

            if action == "all":
                message = (
                    f"{len(selected)} fluxo(s) completo(s) executado(s) " "com sucesso."
                )
            elif action == "update":
                message = f"{len(selected)} base(s) atualizada(s) com sucesso."
            else:
                operation = "exportado" if action == "export" else "redirecionado"
                message = (
                    f"{len(selected)} fluxo(s) e {len(generated)} arquivo(s) "
                    f"{operation}(s) com sucesso."
                )
            report = session.finish(message)
            self.reliability.notifications.add(
                "success",
                "Execução concluída",
                message,
                {
                    "execution_id": session.execution_id,
                    "report": str(report),
                    "company": company_key,
                },
            )
            return {
                "ok": True,
                "message": message,
                "paths": [str(path) for path in generated],
                "execution_id": session.execution_id,
                "report": str(report),
                "artifacts": self._artifact_evidence(generated),
            }
        except SantriAutomationError as error:
            evidence = session.capture_screen() if session else None
            report = session.fail(str(error), evidence) if session else None
            self._record_execution_failure(
                company_key,
                current_workflow,
                action,
                source,
                str(error),
                {
                    "execution_id": session.execution_id if session else "",
                    "evidence": str(evidence or ""),
                    "report": str(report or ""),
                },
            )
            self.reliability.notifications.add(
                "error",
                "Falha na execução",
                str(error),
                {
                    "evidence": str(evidence or ""),
                    "report": str(report or ""),
                },
            )
            return {
                "ok": False,
                "error": str(error),
                "execution_id": session.execution_id if session else "",
                "evidence": str(evidence or ""),
                "report": str(report or ""),
            }
        except Exception as error:
            message = f"Falha inesperada: {type(error).__name__}: {error}"
            evidence = session.capture_screen() if session else None
            report = session.fail(message, evidence) if session else None
            self._record_execution_failure(
                company_key,
                current_workflow,
                action,
                source,
                message,
                {
                    "execution_id": session.execution_id if session else "",
                    "evidence": str(evidence or ""),
                    "report": str(report or ""),
                },
            )
            self.reliability.notifications.add(
                "error",
                "Falha inesperada",
                message,
                {
                    "evidence": str(evidence or ""),
                    "report": str(report or ""),
                },
            )
            return {
                "ok": False,
                "error": message,
                "execution_id": session.execution_id if session else "",
                "evidence": str(evidence or ""),
                "report": str(report or ""),
            }
        finally:
            self._execution_lock.release()

    def _queue_loop(self) -> None:
        while True:
            job = self.execution_queue.claim()
            if job is None:
                self._queue_wake.wait(1.0)
                self._queue_wake.clear()
                continue
            simulation = self.simulator.simulate(
                self.catalog.load(),
                str(job["company"]),
                str(job["workflow_id"]),
                str(job["action"]),
            )
            result = (
                self.run_workflows(
                    str(job["company"]),
                    [str(job["workflow_id"])],
                    str(job["action"]),
                    source="queue",
                    queue_job_id=str(job["id"]),
                )
                if simulation.get("ready")
                else {
                    "ok": False,
                    "error": "Item bloqueado pela simulação preventiva antes da execução.",
                    "simulation": simulation,
                }
            )
            self.execution_queue.finish(str(job["id"]), result)

    def _run_queue_aware_step(
        self,
        queue_job_id: str,
        session: Any,
        workflow_id: str,
        name: str,
        operation: Any,
        retry_count: int,
    ) -> tuple[Path, ...]:
        if queue_job_id and self.execution_queue.cancellation_requested(queue_job_id):
            raise SantriAutomationError(
                "Execução cancelada no ponto seguro entre etapas."
            )
        return session.run_step(
            workflow_id,
            name,
            operation,
            retries=retry_count,
            progress=self._emit_progress,
        )

    @staticmethod
    def _artifact_evidence(
        paths: tuple[Path, ...] | list[Path],
    ) -> list[dict[str, Any]]:
        evidence = []
        for value in paths:
            path = Path(value)
            item: dict[str, Any] = {
                "path": str(path),
                "exists": path.is_file(),
                "size": 0,
                "sha256": "",
            }
            if path.is_file():
                try:
                    item["size"] = path.stat().st_size
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    item["sha256"] = digest.hexdigest()
                except OSError:
                    item["exists"] = False
            evidence.append(item)
        return evidence

    @staticmethod
    def _lifecycle_summary(state: dict[str, Any]) -> dict[str, int]:
        values = [
            str(
                workflow.get("lifecycle")
                or ("production" if workflow.get("implemented") else "draft")
            )
            for company in state.get("companies", {}).values()
            for workflow in company.get("workflows", [])
        ]
        return {
            key: sum(value == key for value in values)
            for key in ("draft", "homologation", "production")
        }

    def _emit_progress(self, message: str) -> None:
        if self.window is None:
            return
        encoded = json.dumps(message, ensure_ascii=False)
        try:
            self.window.evaluate_js(f"window.santriUi?.onProgress({encoded});")
        except Exception:
            pass

    def _record_execution_failure(
        self,
        company_key: str,
        workflow: dict[str, Any] | None,
        action: str,
        source: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._append_history(
            company=company_key,
            workflow_id=str(workflow.get("id") or "") if workflow else "",
            workflow_name=str(workflow.get("name") or "") if workflow else "",
            category="execution",
            action=action,
            status="error",
            source=source,
            message=message,
            details=details or {},
        )

    def _append_history(self, **event: Any) -> None:
        try:
            self.catalog.append_history(event)
        except Exception as error:
            error_path = self.catalog.user_path.parent / "app-errors.log"
            error_path.parent.mkdir(parents=True, exist_ok=True)
            with error_path.open("a", encoding="utf-8") as stream:
                stream.write(
                    f"{datetime.now().astimezone().isoformat()} "
                    f"Falha ao gravar histórico: {type(error).__name__}: {error}\n"
                )

    def _record_scheduler_error(self, error: Exception) -> None:
        self._append_history(
            company="system",
            category="scheduler",
            action="scheduler_error",
            status="error",
            source="system",
            message=f"Falha interna no agendador: {type(error).__name__}: {error}",
        )

    def _validate_company(self, company_key: str) -> None:
        if company_key not in self.catalog.load()["companies"]:
            raise SantriAutomationError(f"Empresa inválida: {company_key}")

    def _detailed_health(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.diagnostics.detailed_health(state)

    def _system_health(self, state: dict[str, Any]) -> dict[str, Any]:
        return self.diagnostics.system_health(state)

    @staticmethod
    def _path_status(path: Path, timeout_seconds: float = 0.4) -> bool | None:
        return SystemDiagnostics.path_status(path, timeout_seconds)


def main() -> None:
    instance = SingleInstance("Local\\SH.SantriExportacoes")
    if not instance.acquired:
        ctypes.windll.user32.MessageBoxW(
            None,
            "O Santri Exportações já está aberto.",
            "Santri Exportações",
            0x40,
        )
        instance.close()
        return
    dashboard = _dashboard_path()
    if not dashboard.exists():
        raise RuntimeError(f"Painel local não encontrado: {dashboard}")

    api = DashboardApi()
    api.catalog.append_history(
        {
            "company": "system",
            "category": "system",
            "action": "application_started",
            "status": "success",
            "source": "system",
            "message": "Aplicativo iniciado.",
        }
    )
    window = webview.create_window(
        "Santri Exportações — Gestão de Exportações",
        url=dashboard.as_uri(),
        width=1380,
        height=860,
        min_size=(1180, 720),
        resizable=True,
        easy_drag=False,
        background_color="#FFFFFF",
    )
    window.expose(
        api.get_state,
        api.open_repository,
        api.run_diagnostics,
        api.copy_operational_summary,
        api.create_support_package,
        api.create_catalog_backup,
        api.restore_catalog_backup,
        api.mark_notifications_read,
        api.clear_notifications,
        api.resume_execution,
        api.dismiss_checkpoint,
        api.export_history_csv,
        api.save_workflow,
        api.save_settings,
        api.delete_workflow,
        api.replicate_workflow,
        api.run_workflows,
        api.check_for_updates,
        api.save_release_preferences,
        api.prepare_update,
        api.rollback_release,
        api.activate_release,
        api.simulate_workflow,
        api.list_workflow_versions,
        api.restore_workflow_version,
        api.enqueue_workflows,
        api.pause_execution_queue,
        api.get_execution_queue,
        api.resume_execution_queue,
        api.cancel_queue_item,
        api.remove_queue_item,
    )
    api.window = window
    configure_startup(
        api.catalog.load()
        .get("settings", {})
        .get(
            "start_with_windows",
            True,
        )
    )
    api.start_scheduler()
    try:
        webview.start(
            gui="edgechromium",
            debug=os.environ.get("SANTRI_WEBVIEW_DEBUG") == "1",
            http_server=True,
            private_mode=False,
            storage_path=str(_user_catalog_path().parent / "webview"),
        )
    finally:
        instance.close()


if __name__ == "__main__":
    main()
