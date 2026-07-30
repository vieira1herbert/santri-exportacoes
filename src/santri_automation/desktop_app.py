from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import webview

from .catalog import ExportCatalog
from .config import load_config
from .resource_paths import resource_path
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
    ) -> None:
        self.window: webview.Window | None = None
        self.catalog = catalog or ExportCatalog(
            _catalog_seed_path(), _user_catalog_path()
        )
        self._driver_factory = driver_factory
        self._config_loader = config_loader
        self._execution_lock = threading.Lock()

    def get_state(self) -> dict[str, Any]:
        return self.catalog.load()

    def save_workflow(
        self,
        company_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_company(company_key)
        return self.catalog.upsert_workflow(company_key, payload)

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.catalog.save_settings(payload)

    def run_workflows(
        self,
        company_key: str,
        workflow_ids: list[str],
        action: str,
    ) -> dict[str, Any]:
        if not self._execution_lock.acquire(blocking=False):
            return {
                "ok": False,
                "error": "Já existe uma operação em andamento.",
            }

        try:
            self._validate_company(company_key)
            if action not in {"export", "redirect", "update"}:
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

            config = (self._config_loader or load_config)(
                _automation_config_path()
            )
            driver = (self._driver_factory or WindowsSantriDriver)(
                config,
                logger=self._emit_progress,
            )
            generated: list[Path] = []

            for workflow in selected:
                if not workflow.get("implemented"):
                    raise SantriAutomationError(
                        f"A exportação “{workflow['name']}” ainda está "
                        "em configuração."
                    )
                if workflow["id"] != "cadastro_produtos":
                    raise SantriAutomationError(
                        f"A automação “{workflow['name']}” ainda não possui "
                        "um executor Windows."
                    )

                self._emit_progress(
                    f"Iniciando o fluxo completo: {workflow['name']}."
                )
                prefix = str(workflow.get("filename_prefix") or "").strip()
                if action == "export":
                    paths = driver.export(
                        company_key,
                        ("sob_encomenda", "completo"),
                        filename_prefix=prefix,
                        downloads_root=downloads_root,
                        existing_file_policy=existing_file_policy,
                        timeout_seconds=timeout_seconds,
                    )
                elif action == "redirect":
                    destination = str(workflow.get("destination") or "").strip()
                    if not destination:
                        raise SantriAutomationError(
                            "Configure a pasta de destino desta exportação."
                        )
                    paths = driver.redirect(
                        company_key,
                        ("sob_encomenda", "completo"),
                        filename_prefix=prefix,
                        destination_root=Path(destination),
                        downloads_root=downloads_root,
                    )
                else:
                    destination = str(workflow.get("destination") or "").strip()
                    if not destination:
                        raise SantriAutomationError(
                            "Configure a pasta de destino desta exportação."
                        )
                    paths = (
                        driver.update_base(
                            company_key,
                            destination_root=Path(destination),
                            timeout_seconds=timeout_seconds,
                        ),
                    )
                generated.extend(paths)
                self.catalog.mark_result(
                    company_key,
                    workflow["id"],
                    (
                        "Base atualizada"
                        if action == "update"
                        else "Concluído"
                    ),
                    datetime.now().strftime("%d/%m · %H:%M"),
                )

            if action == "update":
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
            return {
                "ok": True,
                "message": message,
                "paths": [str(path) for path in generated],
            }
        except SantriAutomationError as error:
            return {"ok": False, "error": str(error)}
        except Exception as error:
            return {
                "ok": False,
                "error": f"Falha inesperada: {type(error).__name__}: {error}",
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

    def _validate_company(self, company_key: str) -> None:
        if company_key not in self.catalog.load()["companies"]:
            raise SantriAutomationError(
                f"Empresa inválida: {company_key}"
            )


def main() -> None:
    dashboard = _dashboard_path()
    if not dashboard.exists():
        raise RuntimeError(f"Painel local não encontrado: {dashboard}")

    api = DashboardApi()
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
    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=False,
        storage_path=str(_user_catalog_path().parent / "webview"),
    )


if __name__ == "__main__":
    main()
