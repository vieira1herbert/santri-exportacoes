from __future__ import annotations

import ctypes
import os
import platform
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..catalog import ExportCatalog
from ..config import load_config
from ..security import SecurityViolation, UpdateScriptPolicy


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
                        if script_status is True:
                            try:
                                UpdateScriptPolicy.authorize(script, destination)
                            except (OSError, SecurityViolation):
                                script_status = False
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
            runtime = self.runtime_status()
            ready = (
                all(item["ready"] for item in companies.values())
                and runtime["session_unlocked"] is True
            )
            return {"ready": ready, "companies": companies, "runtime": runtime}
        except Exception as error:
            return {
                "ready": False,
                "error": f"{type(error).__name__}: {error}",
                "companies": {},
                "runtime": self.runtime_status(),
            }

    def execution_preflight(
        self,
        state: dict[str, Any],
        company_key: str,
        workflow_ids: list[str],
        action: str,
    ) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(name: str, status: bool | None, detail: str, required: bool = True) -> None:
            checks.append(
                {
                    "name": name,
                    "status": "ok" if status is True else "warning" if status is None else "error",
                    "detail": detail,
                    "required": required,
                }
            )

        runtime = self.runtime_status()
        add(
            "Sessão Windows",
            runtime["session_unlocked"],
            "Aberta e desbloqueada" if runtime["session_unlocked"] else "Indisponível ou bloqueada",
        )
        add(
            "Santri em execução",
            runtime["santri_open"].get(company_key, False),
            "Aberto" if runtime["santri_open"].get(company_key) else "Será iniciado automaticamente",
            required=False,
        )
        config = (self.config_loader or load_config)(self.config_path)
        company = config.companies[company_key]
        shortcut = self.path_status(company.shortcut)
        add("Atalho do Santri", shortcut, str(company.shortcut))
        workflows = state["companies"][company_key]["workflows"]
        selected = [item for item in workflows if item.get("id") in set(workflow_ids)]
        if action in {"export", "all"}:
            downloads = Path(
                os.path.expandvars(
                    str(state.get("settings", {}).get("downloads_folder") or "%USERPROFILE%\\Downloads")
                )
            )
            add("Pasta local de exportação", self.path_status(downloads), str(downloads))
        if action in {"redirect", "update", "all"}:
            for workflow in selected:
                destination_text = str(workflow.get("destination") or "").strip()
                destination = Path(destination_text) if destination_text else Path()
                available = self.path_status(destination) if destination_text else False
                add(f"Destino · {workflow.get('name')}", available, str(destination))
                if action in {"update", "all"}:
                    script_name = self._script_name(str(workflow.get("id") or ""))
                    if script_name:
                        script = destination / script_name
                        authorized: bool | None = self.path_status(script)
                        if authorized is True:
                            try:
                                UpdateScriptPolicy.authorize(script, destination)
                            except (OSError, SecurityViolation):
                                authorized = False
                        add(f"Atualizador · {workflow.get('name')}", authorized, str(script))
        failed = sum(
            item["required"] and item["status"] != "ok"
            for item in checks
        )
        return {
            "ready": failed == 0,
            "failed": failed,
            "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "checks": checks,
        }

    @staticmethod
    def runtime_status() -> dict[str, Any]:
        return {
            "session_unlocked": SystemDiagnostics._session_unlocked(),
            "santri_open": SystemDiagnostics._santri_windows(),
        }

    @staticmethod
    def _session_unlocked() -> bool:
        if os.name != "nt":
            return False
        user32 = ctypes.windll.user32
        user32.OpenInputDesktop.restype = ctypes.c_void_p
        user32.CloseDesktop.argtypes = [ctypes.c_void_p]
        handle = user32.OpenInputDesktop(0, False, 0x0100)
        if not handle:
            return False
        user32.CloseDesktop(handle)
        return True

    @staticmethod
    def _santri_windows() -> dict[str, bool]:
        values = {"sol": False, "horus": False}
        if os.name != "nt":
            return values
        try:
            import win32gui

            titles: list[str] = []
            win32gui.EnumWindows(
                lambda handle, result: result.append(win32gui.GetWindowText(handle)),
                titles,
            )
            normalized = [title.casefold() for title in titles if title]
            values["sol"] = any("santri adm - cd sia" in title for title in normalized)
            values["horus"] = any("santri adm - brasilia" in title for title in normalized)
        except Exception:
            return values
        return values

    @staticmethod
    def _script_name(workflow_id: str) -> str:
        return {
            "cadastro_produtos": "ShellCadastroProdutos.ps1",
            "transfer_ncias": "ShellTransferencias.ps1",
            "estoque_disponivel": "ShellEstoqueDisp.ps1",
        }.get(workflow_id, "")

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
