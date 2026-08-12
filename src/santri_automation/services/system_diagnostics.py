from __future__ import annotations

import os
import platform
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..catalog import ExportCatalog
from ..config import load_config


class SystemDiagnostics:
    def __init__(
        self,
        catalog: ExportCatalog,
        config_path: Path,
        config_loader: Callable[..., Any] | None = None,
    ) -> None:
        self.catalog = catalog
        self.config_path = config_path
        self.config_loader = config_loader

    def detailed_health(self, state: dict[str, Any]) -> dict[str, Any]:
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
        downloads_status = self.path_status(downloads)
        add(
            "Arquivos",
            "Pasta local de exportação",
            "ok" if downloads_status is True else "error",
            str(downloads),
        )
        try:
            config = (self.config_loader or load_config)(
                self.config_path
            )
            for company_key, company in config.companies.items():
                shortcut = self.path_status(company.shortcut)
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
                    destination_status = self.path_status(destination)
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
                        script_status = self.path_status(script)
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

    def system_health(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            config = (self.config_loader or load_config)(
                self.config_path
            )
            companies: dict[str, Any] = {}
            for company_key, company in config.companies.items():
                workflows = state["companies"][company_key]["workflows"]
                shortcut_status = self.path_status(company.shortcut)
                destinations = [
                    {
                        "name": workflow["name"],
                        "available": self.path_status(
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
    def path_status(path: Path, timeout_seconds: float = 0.4) -> bool | None:
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
