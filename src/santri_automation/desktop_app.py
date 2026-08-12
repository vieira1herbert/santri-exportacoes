from __future__ import annotations

import ctypes
import csv
import json
import os
import platform
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import webview

from . import __version__
from .catalog import ExportCatalog
from .config import load_config
from .executors import ExecutionContext, ExecutorRegistry, build_default_registry
from .resource_paths import resource_path
from .reliability import ReliabilityCenter
from .scheduler import WorkflowScheduler
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
    return root / "Santri Export" / "export_catalog.json"


class DashboardApi:
    def __init__(
        self,
        catalog: ExportCatalog | None = None,
        driver_factory: Any = None,
        config_loader: Any = None,
        executor_registry: ExecutorRegistry | None = None,
    ) -> None:
        self.window: webview.Window | None = None
        self.catalog = catalog or ExportCatalog(
            _catalog_seed_path(), _user_catalog_path()
        )
        self._driver_factory = driver_factory
        self._config_loader = config_loader
        self._executors = executor_registry or build_default_registry()
        self._execution_lock = threading.Lock()
        self.reliability = ReliabilityCenter(self.catalog.user_path.parent)
        self.scheduler = WorkflowScheduler(
            self.catalog,
            self._run_scheduled_workflow,
            on_error=self._record_scheduler_error,
        )

    def get_state(self) -> dict[str, Any]:
        state = self.catalog.load()
        health = self._system_health(state)
        notifications = self.reliability.notifications.list()
        state["application"] = {
            "version": __version__,
            "health": health,
            "notifications": notifications,
            "unread_notifications": sum(
                not bool(item.get("read")) for item in notifications
            ),
            "pending_checkpoint": self.reliability.pending_checkpoint(),
            "reports": self.reliability.latest_reports(),
            "backups": self.catalog.list_backups(),
        }
        return state

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
            "Santri-Historico-"
            f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
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
        saved = self.catalog.upsert_workflow(company_key, payload)
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
            "message": (
                f"Exportação replicada para {target_company.upper()}."
            ),
        }

    def start_scheduler(self) -> None:
        self.scheduler.start()

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
        if not result.get("ok") and "em andamento" not in str(
            result.get("error") or ""
        ).lower():
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
                raise SantriAutomationError(
                    "Selecione ao menos uma exportação."
                )

            catalog = self.catalog.load()
            settings = catalog.get("settings", {})
            downloads_root = Path(
                os.path.expandvars(
                    str(
                        settings.get("downloads_folder")
                        or "%USERPROFILE%\\Downloads"
                    )
                )
            )
            existing_file_policy = str(
                settings.get("existing_file_policy") or "block"
            )
            timeout_seconds = (
                max(1, int(settings.get("timeout_minutes") or 10))
                * 60
            )
            workflows = catalog["companies"][company_key]["workflows"]
            selected = [
                workflow
                for workflow in workflows
                if workflow["id"] in set(workflow_ids)
            ]
            if len(selected) != len(set(workflow_ids)):
                raise SantriAutomationError(
                    "Uma das exportações selecionadas não foi encontrada."
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
                    message=(
                        f"Execução de “{workflow['name']}” iniciada."
                    ),
                )

            config = (self._config_loader or load_config)(
                _automation_config_path()
            )
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

                self._emit_progress(
                    f"Iniciando o fluxo completo: {workflow['name']}."
                )
                session.record(
                    "workflow",
                    "running",
                    f"Iniciando {workflow['name']}.",
                    {"workflow_id": workflow["id"]},
                )
                prefix = str(workflow.get("filename_prefix") or "").strip()
                destination = str(workflow.get("destination") or "").strip()
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
                    workflow_id=workflow["id"],
                    step_runner=lambda name, operation, workflow_id=workflow["id"]: session.run_step(
                        workflow_id,
                        name,
                        operation,
                        retries=2,
                        progress=self._emit_progress,
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
                        else "Base atualizada"
                        if action == "update"
                        else "Concluído"
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
                    details={"paths": [str(path) for path in paths]},
                )
                session.record(
                    "workflow",
                    "success",
                    f"Fluxo concluído: {workflow['name']}.",
                    {"workflow_id": workflow["id"]},
                )

            if action == "all":
                message = (
                    f"{len(selected)} fluxo(s) completo(s) executado(s) "
                    "com sucesso."
                )
            elif action == "update":
                message = (
                    f"{len(selected)} base(s) atualizada(s) com sucesso."
                )
            else:
                operation = (
                    "exportado" if action == "export" else "redirecionado"
                )
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

    def _emit_progress(self, message: str) -> None:
        if self.window is None:
            return
        encoded = json.dumps(message, ensure_ascii=False)
        try:
            self.window.evaluate_js(
                f"window.santriUi?.onProgress({encoded});"
            )
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
            raise SantriAutomationError(
                f"Empresa inválida: {company_key}"
            )

    def _detailed_health(self, state: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(
            category: str,
            name: str,
            status: str,
            detail: str,
            required: bool = True,
        ) -> None:
            checks.append(
                {
                    "category": category,
                    "name": name,
                    "status": status,
                    "detail": detail,
                    "required": required,
                }
            )

        add(
            "Sistema",
            "Windows",
            "ok" if os.name == "nt" else "error",
            f"{platform.system()} {platform.release()}",
        )
        app_root = self.catalog.user_path.parent
        try:
            app_root.mkdir(parents=True, exist_ok=True)
            probe = app_root / ".diagnostic-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            add("Sistema", "Perfil local", "ok", str(app_root))
        except OSError as error:
            add("Sistema", "Perfil local", "error", str(error))
        try:
            usage = shutil.disk_usage(app_root.anchor or app_root)
            free_gb = usage.free / 1024**3
            add(
                "Sistema",
                "Espaço em disco",
                "ok" if free_gb >= 1 else "warning",
                f"{free_gb:.1f} GB disponíveis",
                required=False,
            )
        except OSError as error:
            add("Sistema", "Espaço em disco", "warning", str(error), False)
        downloads = Path(
            os.path.expandvars(
                str(
                    state.get("settings", {}).get("downloads_folder")
                    or "%USERPROFILE%\\Downloads"
                )
            )
        )
        downloads_status = self._path_status(downloads)
        add(
            "Arquivos",
            "Pasta local de exportação",
            "ok" if downloads_status is True else "error",
            str(downloads),
        )
        try:
            config = (self._config_loader or load_config)(
                _automation_config_path()
            )
            for company_key, company in config.companies.items():
                shortcut = self._path_status(company.shortcut)
                add(
                    company_key.upper(),
                    "Atalho do Santri",
                    "ok" if shortcut is True else "error",
                    str(company.shortcut),
                )
                workflows = state["companies"][company_key]["workflows"]
                for workflow in workflows:
                    if not workflow.get("implemented"):
                        continue
                    destination_text = str(workflow.get("destination") or "")
                    if not destination_text:
                        add(
                            company_key.upper(),
                            workflow["name"],
                            "error",
                            "Destino não configurado.",
                        )
                        continue
                    destination = Path(destination_text)
                    destination_status = self._path_status(destination)
                    add(
                        company_key.upper(),
                        f"Destino · {workflow['name']}",
                        "ok" if destination_status is True else "error",
                        str(destination),
                    )
                    script_name = (
                        "ShellCadastroProdutos.ps1"
                        if workflow["id"] == "cadastro_produtos"
                        else "ShellTransferencias.ps1"
                        if workflow["id"] == "transfer_ncias"
                        else "ShellEstoqueDisp.ps1"
                        if workflow["id"] == "estoque_disponivel"
                        else ""
                    )
                    if script_name:
                        script = destination / script_name
                        script_status = self._path_status(script)
                        add(
                            company_key.upper(),
                            f"Script · {workflow['name']}",
                            "ok" if script_status is True else "error",
                            str(script),
                        )
        except Exception as error:
            add(
                "Configuração",
                "Catálogo de automação",
                "error",
                f"{type(error).__name__}: {error}",
            )
        failed = sum(
            item["required"] and item["status"] != "ok" for item in checks
        )
        return {
            "ready": failed == 0,
            "failed": failed,
            "checked_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "checks": checks,
        }

    def _system_health(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            config = (self._config_loader or load_config)(
                _automation_config_path()
            )
            companies: dict[str, Any] = {}
            for company_key, company in config.companies.items():
                workflows = state["companies"][company_key]["workflows"]
                shortcut_status = self._path_status(company.shortcut)
                destinations = [
                    {
                        "name": workflow["name"],
                        "available": self._path_status(
                            Path(workflow["destination"])
                        ),
                    }
                    for workflow in workflows
                    if workflow.get("implemented")
                    and workflow.get("destination")
                ]
                companies[company_key] = {
                    "shortcut": shortcut_status,
                    "destinations": destinations,
                    "ready": shortcut_status is True
                    and all(item["available"] is True for item in destinations),
                }
            ready = all(item["ready"] for item in companies.values())
            return {"ready": ready, "companies": companies}
        except Exception as error:
            return {
                "ready": False,
                "error": f"{type(error).__name__}: {error}",
                "companies": {},
            }

    @staticmethod
    def _path_status(path: Path, timeout_seconds: float = 0.4) -> bool | None:
        result: dict[str, bool] = {}

        def check() -> None:
            try:
                result["available"] = path.exists()
            except OSError:
                result["available"] = False

        thread = threading.Thread(target=check, daemon=True)
        thread.start()
        thread.join(timeout_seconds)
        return result.get("available")


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
        js_api=api,
        width=1220,
        height=820,
        min_size=(980, 680),
        resizable=True,
        easy_drag=False,
        background_color="#FFFFFF",
    )
    api.window = window
    configure_startup(
        api.catalog.load().get("settings", {}).get(
            "start_with_windows",
            True,
        )
    )
    api.start_scheduler()
    try:
        webview.start(
            gui="edgechromium",
            debug=False,
            private_mode=False,
            storage_path=str(_user_catalog_path().parent / "webview"),
        )
    finally:
        instance.close()


if __name__ == "__main__":
    main()
