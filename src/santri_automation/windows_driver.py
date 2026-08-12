from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path

from pywinauto import Desktop, keyboard, mouse
from pywinauto.controls.hwndwrapper import HwndWrapper
from pywinauto.timings import TimeoutError as PywinautoTimeoutError

from .config import AutomationConfig, CompanyDefinition, ExportDefinition


LogCallback = Callable[[str], None]


class SantriAutomationError(RuntimeError):
    pass


class WindowsSantriDriver:
    MAIN_TITLES = {
        "sol": "Santri ADM - CD SIA",
        "horus": "Santri ADM - BRASILIA",
    }
    REPORT_CLASS = "TFormRelacaoProdutos"
    REPORT_MENU_PATH = "$803->$837->$838"
    TRANSFER_REPORT_CLASS = "TFormRelacaoTransferencias"
    TRANSFER_REPORT_MENU_PATH = "$803->$995->$1002->$1003"
    COMPANY_SELECTOR_TITLE = "Grupo SH - Login"
    COMPANY_SELECTOR_COORDS = {
        "sol": (126, 193),
        "horus": (319, 193),
    }
    AUTHORIZED_COMPANY_STEPS = {
        "sol": 2,
        "horus": 0,
    }

    FILTERS_OUTER_TAB = (170, 47)
    FILTERS_MAIN_TAB = (205, 76)
    FILTERS_SECONDARY_TAB = (320, 76)
    PROCESS_BUTTON = (70, 50)
    SPREADSHEET_BUTTON = (70, 458)
    SPREADSHEET_SUCCESS_OK = (609, 453)
    GROUP_BY_PRODUCT_RADIO = (870, 812)
    SOB_ENCOMENDA_TARGET = (1118, 598)
    TRANSFER_COMPANY_SEARCH = (642, 95)
    TRANSFER_START_DATE = (734, 176)
    TRANSFER_END_DATE = (875, 176)
    TRANSFER_MARK_ALL_STATUS = (1015, 324)
    TRANSFER_SPREADSHEET_BUTTON = (70, 608)
    TRANSFER_ANALYTIC_OPTION = (25, 75)
    TRANSFER_ANALYTIC_OK = (70, 195)
    TRANSFER_READING_FOLDER = "EXPORTACAO - Base de Transferencias"
    TRANSFER_SCRIPT = "ShellTransferencias.ps1"
    STOCK_REPORT_TITLE = "Relação de Valor do Estoque"
    STOCK_REPORT_MENU_PATH = "$803->$995->$1056"
    STOCK_ASSET_TARGET = (802, 310)
    STOCK_CONSUMPTION_TARGET = (865, 365)
    STOCK_SPREADSHEET_BUTTON = (70, 488)
    STOCK_PROCESS_YES = (497, 484)
    STOCK_RESULT_TAB = (235, 47)
    STOCK_READING_FOLDER = "PASTA LEITURA - Arquivo ODS para XLXS"
    STOCK_SCRIPT = "ShellEstoqueDisp.ps1"

    def __init__(
        self,
        config: AutomationConfig,
        logger: LogCallback | None = None,
    ) -> None:
        self.config = config
        self.log = logger or (lambda _message: None)

    def export(
        self,
        company_key: str,
        export_keys: Iterable[str],
        execution_date: date | None = None,
        filename_prefix: str | None = None,
        downloads_root: Path | None = None,
        existing_file_policy: str = "block",
        timeout_seconds: int = 600,
    ) -> tuple[Path, ...]:
        company = self._company(company_key)
        selected = self._exports(export_keys)
        current_date = execution_date or date.today()

        main = self._get_or_open_main(company_key, company)
        relation = self._get_or_open_relation(main)
        created: list[Path] = []

        for export in selected:
            destination = self._downloads_path(
                company,
                export,
                current_date,
                filename_prefix,
                downloads_root,
            )
            if destination.exists():
                if existing_file_policy == "replace":
                    if not destination.is_file():
                        raise SantriAutomationError(
                            f"O destino existente não é um arquivo: "
                            f"{destination}."
                        )
                    destination.unlink()
                    self.log(
                        f"Arquivo anterior apagado: {destination.name}."
                    )
                else:
                    raise SantriAutomationError(
                        f"O arquivo já existe em Downloads: "
                        f"{destination.name}. Mova ou renomeie o arquivo "
                        "antes de repetir a exportação."
                    )

            self.log(f"Configurando {export.name}...")
            self._configure_export(relation, export.key)
            self.log(f"Processando {export.name} no Santri...")
            relation.click_input(coords=self.PROCESS_BUTTON)
            self._wait_for_result(
                relation,
                timeout_seconds=timeout_seconds,
            )
            self.log(f"Salvando {destination.name}...")
            self._export_spreadsheet(relation, destination)
            self._validate_ods_file(destination)
            created.append(destination)
            self.log(f"Arquivo criado: {destination}")

        self._return_to_main(relation, main)
        return tuple(created)

    def redirect(
        self,
        company_key: str,
        export_keys: Iterable[str],
        execution_date: date | None = None,
        filename_prefix: str | None = None,
        destination_root: Path | None = None,
        downloads_root: Path | None = None,
        backup_root: Path | None = None,
    ) -> tuple[Path, ...]:
        company = self._company(company_key)
        selected = self._exports(export_keys)
        current_date = execution_date or date.today()
        moved: list[Path] = []
        root = (destination_root or company.network_root).resolve()
        self._validate_company_root(company, root)
        prepared: list[tuple[Path, Path]] = []

        for export in selected:
            source = self._downloads_path(
                company,
                export,
                current_date,
                filename_prefix,
                downloads_root,
            )
            destination = self._network_path(
                company,
                export,
                current_date,
                filename_prefix,
                destination_root,
            )
            if not source.exists():
                raise SantriAutomationError(
                    f"Arquivo não encontrado em Downloads: {source.name}"
                )
            self._validate_ods_file(source)
            self._validate_destination_folder(destination.parent, root)
            prepared.append((source, destination))

        local_app_data = Path(
            os.environ.get("LOCALAPPDATA")
            or Path.home() / "AppData" / "Local"
        )
        backups = backup_root or local_app_data / "Santri Export" / "file-backups"
        session = (
            backups
            / company_key
            / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )
        folders = {destination.parent for _, destination in prepared}

        with tempfile.TemporaryDirectory(prefix="santri-redirect-") as temporary:
            staging = Path(temporary)
            staged: list[tuple[Path, Path, Path]] = []
            for index, (source, destination) in enumerate(prepared):
                staged_file = staging / f"{index}-{destination.name}"
                shutil.copy2(source, staged_file)
                self._validate_ods_file(staged_file)
                staged.append((source, staged_file, destination))

            self._backup_destination_folders(folders, root, session)
            try:
                for folder in folders:
                    self._clear_destination_folder(folder, root)
                for source, staged_file, destination in staged:
                    self.log(f"Redirecionando {source.name}...")
                    shutil.copy2(staged_file, destination)
                    self._validate_ods_file(destination)
                    moved.append(destination)
                    self.log(f"Arquivo enviado para: {destination.parent}")
            except Exception as error:
                self._restore_destination_folders(folders, root, session)
                raise SantriAutomationError(
                    "O redirecionamento falhou e os arquivos anteriores foram restaurados."
                ) from error

        for source, _ in prepared:
            source.unlink()
        self._rotate_file_backups(backups / company_key)

        self.log(
            "Redirecionamento concluído. Use “Atualizar Base” para converter "
            "os arquivos e atualizar o Power Query."
        )
        return tuple(moved)

    def export_transferencias(
        self,
        company_key: str,
        start_date: date,
        end_date: date,
        filename_prefix: str | None = None,
        downloads_root: Path | None = None,
        existing_file_policy: str = "block",
        timeout_seconds: int = 600,
    ) -> tuple[Path, ...]:
        if start_date > end_date:
            raise SantriAutomationError(
                "A data inicial não pode ser posterior à data final."
            )
        company = self._company(company_key)
        destination = self._transfer_downloads_path(
            company,
            end_date,
            filename_prefix,
            downloads_root,
        )
        self._prepare_download_destination(
            destination,
            existing_file_policy,
        )
        main = self._get_or_open_main(company_key, company)
        relation = self._get_or_open_transfer_relation(main)
        self.log("Configurando empresas, período e status de Transferências...")
        self._configure_transferencias(relation, start_date, end_date)
        self.log("Processando Transferências no Santri...")
        relation.click_input(coords=self.PROCESS_BUTTON)
        self._wait_for_result(
            relation,
            timeout_seconds=timeout_seconds,
        )
        self.log(f"Salvando {destination.name}...")
        self._export_spreadsheet(
            relation,
            destination,
            button_coords=self.TRANSFER_SPREADSHEET_BUTTON,
            confirm_analytic=True,
        )
        self._validate_ods_file(destination)
        self.log(f"Arquivo criado: {destination}")
        self._return_to_main(relation, main)
        return (destination,)

    def redirect_transferencias(
        self,
        company_key: str,
        execution_date: date,
        filename_prefix: str | None,
        destination_root: Path,
        downloads_root: Path | None = None,
        backup_root: Path | None = None,
    ) -> tuple[Path, ...]:
        company = self._company(company_key)
        root = destination_root.resolve()
        self._validate_transfer_root(company, root)
        source = self._transfer_downloads_path(
            company,
            execution_date,
            filename_prefix,
            downloads_root,
        )
        if not source.exists():
            raise SantriAutomationError(
                f"Arquivo não encontrado em Downloads: {source.name}"
            )
        self._validate_ods_file(source)
        folder = root / self.TRANSFER_READING_FOLDER
        self._validate_destination_folder(folder, root)
        destination = folder / source.name
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA")
            or Path.home() / "AppData" / "Local"
        )
        backups = backup_root or local_app_data / "Santri Export" / "file-backups"
        session = (
            backups
            / company_key
            / "transferencias"
            / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )
        with tempfile.TemporaryDirectory(prefix="santri-transfer-redirect-") as temporary:
            staged = Path(temporary) / source.name
            shutil.copy2(source, staged)
            self._validate_ods_file(staged)
            self._backup_destination_folders({folder}, root, session)
            try:
                self._clear_destination_folder(folder, root)
                shutil.copy2(staged, destination)
                self._validate_ods_file(destination)
            except Exception as error:
                self._restore_destination_folders({folder}, root, session)
                raise SantriAutomationError(
                    "O redirecionamento falhou e o arquivo anterior foi restaurado."
                ) from error
        source.unlink()
        self._rotate_file_backups(backups / company_key / "transferencias")
        self.log(f"Arquivo enviado para: {folder}")
        return (destination,)

    def export_estoque_disponivel(
        self,
        company_key: str,
        include_asset_consumption: bool,
        execution_date: date | None = None,
        filename_prefix: str | None = None,
        downloads_root: Path | None = None,
        existing_file_policy: str = "block",
        timeout_seconds: int = 600,
    ) -> tuple[Path, ...]:
        company = self._company(company_key)
        current_date = execution_date or date.today()
        destination = self._stock_downloads_path(
            company,
            current_date,
            filename_prefix,
            downloads_root,
        )
        self._prepare_download_destination(destination, existing_file_policy)
        main = self._get_or_open_main(company_key, company)
        relation = self._get_or_open_stock_relation(main)
        self.log("Selecionando todas as empresas do Estoque Disponível...")
        self._configure_stock_relation(relation, include_asset_consumption)
        self.log("Processando Estoque Disponível no Santri...")
        relation.click_input(coords=self.PROCESS_BUTTON)
        self._confirm_long_process(relation)
        self._wait_for_result(
            relation,
            timeout_seconds=timeout_seconds,
            activate_result_tab=True,
        )
        self.log(f"Salvando {destination.name}...")
        self._export_spreadsheet(
            relation,
            destination,
            button_coords=self.STOCK_SPREADSHEET_BUTTON,
            confirm_stock_model=True,
        )
        self._validate_ods_file(destination)
        self.log(f"Arquivo criado: {destination}")
        self._return_to_main(relation, main)
        return (destination,)

    def redirect_estoque_disponivel(
        self,
        company_key: str,
        filename_prefix: str | None,
        destination_root: Path,
        execution_date: date | None = None,
        downloads_root: Path | None = None,
        backup_root: Path | None = None,
    ) -> tuple[Path, ...]:
        company = self._company(company_key)
        current_date = execution_date or date.today()
        root = destination_root.resolve()
        self._validate_stock_root(company, root)
        source = self._stock_downloads_path(
            company,
            current_date,
            filename_prefix,
            downloads_root,
        )
        if not source.exists():
            raise SantriAutomationError(
                f"Arquivo não encontrado em Downloads: {source.name}"
            )
        self._validate_ods_file(source)
        folder = root / self.STOCK_READING_FOLDER
        self._validate_destination_folder(folder, root)
        destination = folder / source.name
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA")
            or Path.home() / "AppData" / "Local"
        )
        backups = backup_root or local_app_data / "Santri Export" / "file-backups"
        session = (
            backups
            / company_key
            / "estoque_disponivel"
            / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )
        with tempfile.TemporaryDirectory(prefix="santri-stock-redirect-") as temporary:
            staged = Path(temporary) / source.name
            shutil.copy2(source, staged)
            self._validate_ods_file(staged)
            self._backup_destination_folders({folder}, root, session)
            try:
                self._clear_destination_folder(folder, root)
                shutil.copy2(staged, destination)
                self._validate_ods_file(destination)
            except Exception as error:
                self._restore_destination_folders({folder}, root, session)
                raise SantriAutomationError(
                    "O redirecionamento falhou e o arquivo anterior foi restaurado."
                ) from error
        source.unlink()
        self._rotate_file_backups(backups / company_key / "estoque_disponivel")
        self.log(f"Arquivo enviado para: {folder}")
        return (destination,)

    def _backup_destination_folders(
        self,
        folders: set[Path],
        destination_root: Path,
        session: Path,
    ) -> None:
        for folder in folders:
            self._validate_destination_folder(folder, destination_root)
            folder.mkdir(parents=True, exist_ok=True)
            backup_folder = session / folder.name
            backup_folder.mkdir(parents=True, exist_ok=True)
            for item in folder.iterdir():
                if item.is_symlink():
                    raise SantriAutomationError(
                        f"Link simbólico não permitido na pasta de leitura: {item}"
                    )
                target = backup_folder / item.name
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)

    def _restore_destination_folders(
        self,
        folders: set[Path],
        destination_root: Path,
        session: Path,
    ) -> None:
        for folder in folders:
            self._clear_destination_folder(folder, destination_root)
            backup_folder = session / folder.name
            if not backup_folder.exists():
                continue
            for item in backup_folder.iterdir():
                target = folder / item.name
                if item.is_dir():
                    shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)

    @staticmethod
    def _rotate_file_backups(company_root: Path) -> None:
        if not company_root.exists():
            return
        sessions = sorted(
            (path for path in company_root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for expired in sessions[10:]:
            shutil.rmtree(expired)

    def update_base(
        self,
        company_key: str,
        destination_root: Path,
        timeout_seconds: int = 600,
    ) -> Path:
        company = self._company(company_key)
        root = destination_root.resolve()
        self._validate_company_root(company, root)
        if not root.exists() or not root.is_dir():
            raise SantriAutomationError(
                f"Pasta do Cadastro de Produtos não encontrada: {root}"
            )

        script = root / "ShellCadastroProdutos.ps1"
        if not script.is_file() or script.parent.resolve() != root:
            raise SantriAutomationError(
                f"ShellCadastroProdutos.ps1 não encontrado em: {root}"
            )

        command = self._script_command_without_pause(script)
        self.log(
            f"Atualizando a base da {company.label} com "
            "ShellCadastroProdutos.ps1..."
        )
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                cwd=root,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as error:
            raise SantriAutomationError(
                "A atualização da base excedeu o tempo limite configurado."
            ) from error

        output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part and part.strip()
        )
        if (
            result.returncode != 0
            or "FIM DA EXECUCAO COM ERRO" in output
            or "Processo finalizado com sucesso." not in output
        ):
            detail = output[-1200:] if output else "Sem detalhes adicionais."
            raise SantriAutomationError(
                f"Falha ao atualizar a base da {company.label}: {detail}"
            )

        self.log("Conversão concluída e Power Query atualizado com sucesso.")
        return script

    def update_transferencias(
        self,
        company_key: str,
        destination_root: Path,
        timeout_seconds: int = 600,
    ) -> Path:
        company = self._company(company_key)
        root = destination_root.resolve()
        self._validate_transfer_root(company, root)
        return self._run_update_script(
            company,
            root,
            self.TRANSFER_SCRIPT,
            timeout_seconds,
        )

    def update_estoque_disponivel(
        self,
        company_key: str,
        destination_root: Path,
        timeout_seconds: int = 600,
    ) -> Path:
        company = self._company(company_key)
        root = destination_root.resolve()
        self._validate_stock_root(company, root)
        return self._run_update_script(
            company,
            root,
            self.STOCK_SCRIPT,
            timeout_seconds,
        )

    def _run_update_script(
        self,
        company: CompanyDefinition,
        root: Path,
        script_name: str,
        timeout_seconds: int,
    ) -> Path:
        if not root.exists() or not root.is_dir():
            raise SantriAutomationError(
                f"Pasta da automação não encontrada: {root}"
            )
        script = root / script_name
        if not script.is_file() or script.parent.resolve() != root:
            raise SantriAutomationError(
                f"{script_name} não encontrado em: {root}"
            )
        command = self._script_command_without_pause(script)
        self.log(f"Atualizando a base da {company.label} com {script_name}...")
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    command,
                ],
                cwd=root,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as error:
            raise SantriAutomationError(
                "A atualização da base excedeu o tempo limite configurado."
            ) from error
        output = "\n".join(
            part.strip()
            for part in (result.stdout, result.stderr)
            if part and part.strip()
        )
        if (
            result.returncode != 0
            or "FIM DA EXECUCAO COM ERRO" in output
            or not any(
                marker in output
                for marker in (
                    "Processo finalizado com sucesso.",
                    "Importacao para o Access concluida com sucesso.",
                    "FIM DA EXECUCAO",
                )
            )
        ):
            detail = output[-1200:] if output else "Sem detalhes adicionais."
            raise SantriAutomationError(
                f"Falha ao atualizar a base da {company.label}: {detail}"
            )
        self.log("Conversão concluída e Power Query atualizado com sucesso.")
        return script

    @staticmethod
    def _script_command_without_pause(script: Path) -> str:
        escaped_script = str(script).replace("'", "''")
        return (
            f"$scriptSource = Get-Content -LiteralPath '{escaped_script}' -Raw; "
            "$scriptSource = [regex]::Replace("
            "$scriptSource, '(?im)^\\s*pause\\s*$', ''); "
            "& ([scriptblock]::Create($scriptSource))"
        )

    def _clear_destination_folder(
        self,
        folder: Path,
        destination_root: Path,
    ) -> None:
        self._validate_destination_folder(folder, destination_root)
        folder.mkdir(parents=True, exist_ok=True)
        removed = 0
        for item in folder.iterdir():
            if item.is_symlink() or item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
            removed += 1
        self.log(
            f"Pasta de leitura limpa: {folder} ({removed} item(ns) removido(s))."
        )

    @staticmethod
    def _validate_destination_folder(
        folder: Path,
        destination_root: Path,
    ) -> None:
        root = destination_root.resolve()
        resolved = folder.resolve()
        if resolved == root or resolved.parent != root:
            raise SantriAutomationError(
                "A limpeza foi bloqueada porque a pasta de leitura não é uma "
                f"subpasta direta do destino configurado: {resolved}"
            )

    @staticmethod
    def _validate_company_root(
        company: CompanyDefinition,
        destination_root: Path,
    ) -> None:
        expected = company.network_root.resolve()
        if destination_root.resolve() != expected:
            raise SantriAutomationError(
                f"Destino não autorizado para {company.label}: "
                f"{destination_root}"
            )

    @staticmethod
    def _validate_transfer_root(
        company: CompanyDefinition,
        destination_root: Path,
    ) -> None:
        expected = (company.network_root.parent / "Transferencias").resolve()
        if destination_root.resolve() != expected:
            raise SantriAutomationError(
                f"Destino de Transferências não autorizado para "
                f"{company.label}: {destination_root}"
            )

    @staticmethod
    def _validate_stock_root(
        company: CompanyDefinition,
        destination_root: Path,
    ) -> None:
        base = (
            company.network_root.parent / "Gestao de Estoque Disponivel"
        ).resolve()
        resolved = destination_root.resolve()
        if resolved.parent != base:
            raise SantriAutomationError(
                f"Destino mensal de Estoque Disponível não autorizado para "
                f"{company.label}: {destination_root}"
            )

    @staticmethod
    def _validate_ods_file(path: Path) -> None:
        if not path.is_file() or path.stat().st_size < 1024:
            raise SantriAutomationError(
                f"O arquivo parece incompleto: {path.name}"
            )
        try:
            with zipfile.ZipFile(path) as archive:
                mimetype = archive.read("mimetype").decode("ascii").strip()
        except (OSError, KeyError, UnicodeDecodeError, zipfile.BadZipFile) as error:
            raise SantriAutomationError(
                f"O arquivo não é uma planilha ODS válida: {path.name}"
            ) from error
        if mimetype != "application/vnd.oasis.opendocument.spreadsheet":
            raise SantriAutomationError(
                f"O arquivo não é uma planilha ODS válida: {path.name}"
            )

    def _get_or_open_main(
        self,
        company_key: str,
        company: CompanyDefinition,
    ) -> HwndWrapper:
        title = self.MAIN_TITLES[company_key]
        desktop = Desktop(backend="win32")
        spec = desktop.window(title=title)

        if not spec.exists(timeout=1):
            selector = desktop.window(title=self.COMPANY_SELECTOR_TITLE)
            authorized = desktop.window(title="Empresas Autorizadas")
            if authorized.exists(timeout=1):
                self._select_authorized(
                    authorized.wrapper_object(),
                    company_key,
                )
            elif not selector.exists(timeout=1):
                self.log(f"Abrindo o Santri da {company.label}...")
                shortcut = company.shortcut
                if not shortcut.exists():
                    raise SantriAutomationError(
                        f"Atalho do Santri não encontrado: {shortcut}"
                    )
                os.startfile(shortcut)
                self._wait_and_select_company(company_key, desktop, spec)
            else:
                self._select_company(selector.wrapper_object(), company_key)
                self._wait_and_select_authorized(
                    company_key,
                    desktop,
                    spec,
                )
            try:
                spec.wait("exists visible", timeout=90)
            except PywinautoTimeoutError as error:
                raise SantriAutomationError(
                    "O Santri foi aberto, mas a tela principal não apareceu "
                    "depois da seleção da empresa."
                ) from error

        main = spec.wrapper_object()
        self._ensure_main_maximized(main)
        return main

    def _ensure_main_maximized(self, main: HwndWrapper) -> None:
        if main.is_minimized():
            main.restore()
        for _ in range(3):
            main.maximize()
            time.sleep(0.35)
            if main.is_maximized():
                main.set_focus()
                return
        raise SantriAutomationError(
            "Não foi possível manter a janela principal do Santri maximizada."
        )

    def _prepare_relation_window(
        self,
        main: HwndWrapper,
        relation: HwndWrapper,
    ) -> None:
        if relation.is_maximized():
            relation.restore()
            time.sleep(0.3)
        self._ensure_main_maximized(main)
        relation.set_focus()

    def _wait_and_select_company(
        self,
        company_key: str,
        desktop: Desktop,
        main_spec,
    ) -> None:
        selector = desktop.window(title=self.COMPANY_SELECTOR_TITLE)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if main_spec.exists(timeout=0.2):
                return
            if selector.exists(timeout=0.2):
                self._select_company(
                    selector.wrapper_object(),
                    company_key,
                )
                self._wait_and_select_authorized(
                    company_key,
                    desktop,
                    main_spec,
                )
                return
            time.sleep(0.5)
        raise SantriAutomationError(
            "O seletor SOL/HORUS não apareceu."
        )

    def _select_company(
        self,
        selector: HwndWrapper,
        company_key: str,
    ) -> None:
        self.log(
            "Selecionando 1045 (SOL)..."
            if company_key == "sol"
            else "Selecionando 753 (HORUS)..."
        )
        selector.set_focus()
        selector.click_input(
            coords=self.COMPANY_SELECTOR_COORDS[company_key]
        )

    def _wait_and_select_authorized(
        self,
        company_key: str,
        desktop: Desktop,
        main_spec,
    ) -> None:
        authorized = desktop.window(title="Empresas Autorizadas")
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if main_spec.exists(timeout=0.2):
                return
            if authorized.exists(timeout=0.2):
                self._select_authorized(
                    authorized.wrapper_object(),
                    company_key,
                )
                return
            time.sleep(0.5)
        raise SantriAutomationError(
            "A tela Empresas Autorizadas não apareceu."
        )

    def _select_authorized(
        self,
        window: HwndWrapper,
        company_key: str,
    ) -> None:
        self.log(
            "Selecionando 9 - CD - DF..."
            if company_key == "sol"
            else "Selecionando 1 - BRASILIA..."
        )
        window.set_focus()
        window.click_input(coords=(90, 85))
        keyboard.send_keys("{HOME}")
        for _ in range(self.AUTHORIZED_COMPANY_STEPS[company_key]):
            keyboard.send_keys("{DOWN}")
            time.sleep(0.12)
        keyboard.send_keys("{ENTER}")

    def _get_or_open_relation(self, main: HwndWrapper) -> HwndWrapper:
        relation = self._find_relation(main)
        if relation is None:
            self.log("Abrindo Relatórios > Produtos > Produtos...")
            main.menu_select(self.REPORT_MENU_PATH)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                relation = self._find_relation(main)
                if relation is not None:
                    break
                time.sleep(0.5)
        if relation is None:
            raise SantriAutomationError(
                "Não foi possível abrir a Relação de Produtos."
            )
        self._prepare_relation_window(main, relation)
        return relation

    def _find_relation(
        self,
        main: HwndWrapper,
    ) -> HwndWrapper | None:
        for control in main.descendants():
            if (
                control.class_name() == self.REPORT_CLASS
                and control.is_visible()
            ):
                return control
        return None

    def _get_or_open_transfer_relation(
        self,
        main: HwndWrapper,
    ) -> HwndWrapper:
        relation = self._find_transfer_relation(main)
        if relation is None:
            self.log(
                "Abrindo Relatórios > Estoque > Transferências > "
                "Transferências..."
            )
            main.menu_select(self.TRANSFER_REPORT_MENU_PATH)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                relation = self._find_transfer_relation(main)
                if relation is not None:
                    break
                time.sleep(0.5)
        if relation is None:
            raise SantriAutomationError(
                "Não foi possível abrir a Relação de Transferências."
            )
        self._prepare_relation_window(main, relation)
        return relation

    def _find_transfer_relation(
        self,
        main: HwndWrapper,
    ) -> HwndWrapper | None:
        for control in main.descendants():
            title = control.window_text()
            if not control.is_visible():
                continue
            if control.class_name() == self.TRANSFER_REPORT_CLASS:
                return control
            if "Relação de Transferências" in title:
                return control
        return None

    def _get_or_open_stock_relation(
        self,
        main: HwndWrapper,
    ) -> HwndWrapper:
        relation = self._find_stock_relation(main)
        if relation is None:
            self.log("Abrindo Relatórios > Estoque > Valor do estoque...")
            main.menu_select(self.STOCK_REPORT_MENU_PATH)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                relation = self._find_stock_relation(main)
                if relation is not None:
                    break
                time.sleep(0.5)
        if relation is None:
            raise SantriAutomationError(
                "Não foi possível abrir a Relação de Valor do Estoque."
            )
        self._prepare_relation_window(main, relation)
        return relation

    def _find_stock_relation(
        self,
        main: HwndWrapper,
    ) -> HwndWrapper | None:
        for control in main.descendants():
            if not control.is_visible():
                continue
            if self.STOCK_REPORT_TITLE in control.window_text():
                return control
        return None

    def _configure_stock_relation(
        self,
        relation: HwndWrapper,
        include_asset_consumption: bool,
    ) -> None:
        relation.click_input(coords=self.FILTERS_OUTER_TAB)
        time.sleep(0.4)
        relation.click_input(coords=self.TRANSFER_COMPANY_SEARCH)
        selector = Desktop(backend="win32").window(title="Pesquisa de Empresas")
        try:
            selector.wait("exists visible enabled", timeout=20)
        except PywinautoTimeoutError as error:
            raise SantriAutomationError(
                "A pesquisa de empresas do Estoque Disponível não foi aberta."
            ) from error
        search = selector.wrapper_object()
        search.set_focus()
        search.click_input(coords=(540, 70))
        keyboard.send_keys("{ENTER}")
        time.sleep(1.5)
        keyboard.send_keys("^t")
        time.sleep(0.5)
        search.click_input(coords=(70, 442))
        try:
            selector.wait_not("visible", timeout=10)
        except PywinautoTimeoutError as error:
            raise SantriAutomationError(
                "Não foi possível confirmar as empresas selecionadas."
            ) from error
        if not include_asset_consumption:
            self.log("Filtros Ativo imobilizado e Uso e consumo foram ignorados.")
            return
        asset = self._nearest_control(
            relation,
            self.STOCK_ASSET_TARGET,
            {"TComboBox", "TXComboBox"},
            "Ativo imobilizado",
        )
        consumption = self._nearest_control(
            relation,
            self.STOCK_CONSUMPTION_TARGET,
            {"TComboBox", "TXComboBox"},
            "Uso e consumo",
        )
        self._select_combo_text(asset, "Não")
        self._select_combo_text(consumption, "Não")
        self.log("Ativo imobilizado e Uso e consumo definidos como Não.")

    def _confirm_long_process(self, relation: HwndWrapper) -> None:
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            for window in Desktop(backend="win32").windows(visible_only=True):
                texts = [window.window_text()]
                try:
                    texts.extend(
                        control.window_text()
                        for control in window.descendants()
                    )
                except Exception:
                    pass
                joined = " ".join(texts).lower()
                if "processo poderá levar alguns minutos" not in joined:
                    continue
                window.set_focus()
                for control in window.descendants():
                    if control.window_text().strip().lower() == "sim":
                        control.click_input()
                        return
                keyboard.send_keys("{ENTER}")
                return
            time.sleep(0.3)
        rectangle = relation.rectangle()
        mouse.click(
            coords=(
                rectangle.left + self.STOCK_PROCESS_YES[0],
                rectangle.top + self.STOCK_PROCESS_YES[1],
            )
        )
        time.sleep(0.8)
        self.log("Confirmação de processamento acionada.")

    def _configure_transferencias(
        self,
        relation: HwndWrapper,
        start_date: date,
        end_date: date,
    ) -> None:
        relation.click_input(coords=self.FILTERS_OUTER_TAB)
        time.sleep(0.4)
        relation.click_input(coords=self.TRANSFER_COMPANY_SEARCH)
        selector = Desktop(backend="win32").window(
            title="Pesquisa de Empresas"
        )
        try:
            selector.wait("exists visible enabled", timeout=20)
        except PywinautoTimeoutError as error:
            raise SantriAutomationError(
                "A pesquisa de empresas de origem não foi aberta."
            ) from error
        search = selector.wrapper_object()
        search.set_focus()
        search.click_input(coords=(540, 70))
        keyboard.send_keys("{ENTER}")
        time.sleep(1.5)
        keyboard.send_keys("^t")
        time.sleep(0.5)
        search.click_input(coords=(70, 442))
        try:
            selector.wait_not("visible", timeout=10)
        except PywinautoTimeoutError as error:
            raise SantriAutomationError(
                "Não foi possível confirmar as empresas de origem."
            ) from error
        self._set_date_at(relation, self.TRANSFER_START_DATE, start_date)
        self._set_date_at(relation, self.TRANSFER_END_DATE, end_date)
        relation.click_input(coords=self.TRANSFER_MARK_ALL_STATUS)
        time.sleep(0.5)

    @staticmethod
    def _set_date_at(
        relation: HwndWrapper,
        target: tuple[int, int],
        value: date,
    ) -> None:
        relation.click_input(coords=target)
        keyboard.send_keys("{HOME}")
        keyboard.send_keys(value.strftime("%d%m%Y"))
        time.sleep(0.2)

    def _nearest_control(
        self,
        relation: HwndWrapper,
        target: tuple[int, int],
        classes: set[str],
        field_name: str,
    ) -> HwndWrapper:
        root = relation.rectangle()
        candidates: list[tuple[float, HwndWrapper]] = []
        for control in relation.descendants():
            if control.class_name() not in classes or not control.is_visible():
                continue
            rectangle = control.rectangle()
            center_x = (rectangle.left + rectangle.right) / 2 - root.left
            center_y = (rectangle.top + rectangle.bottom) / 2 - root.top
            distance = (center_x - target[0]) ** 2 + (center_y - target[1]) ** 2
            candidates.append((distance, control))
        if not candidates:
            raise SantriAutomationError(f"O campo {field_name} não foi encontrado.")
        candidates.sort(key=lambda item: item[0])
        distance, control = candidates[0]
        if distance > 70**2:
            raise SantriAutomationError(
                f"A posição do campo {field_name} mudou no Santri."
            )
        return control

    @staticmethod
    def _set_date_control(control: HwndWrapper, value: date) -> None:
        formatted = value.strftime("%d/%m/%Y")
        control.set_focus()
        try:
            control.set_edit_text(formatted)
        except Exception:
            keyboard.send_keys("^a")
            keyboard.send_keys(formatted)
        time.sleep(0.2)

    def _configure_export(
        self,
        relation: HwndWrapper,
        export_key: str,
    ) -> None:
        relation.click_input(coords=self.FILTERS_OUTER_TAB)
        time.sleep(0.4)
        relation.click_input(coords=self.FILTERS_MAIN_TAB)
        time.sleep(0.4)
        combo = self._nearest_combo(
            relation,
            self.SOB_ENCOMENDA_TARGET,
        )

        if export_key == "sob_encomenda":
            self._select_combo_text(combo, "Sim")
            return

        if export_key == "completo":
            self._select_combo_text(combo, "Não filtrar")
            relation.click_input(coords=self.FILTERS_SECONDARY_TAB)
            time.sleep(0.4)
            relation.click_input(coords=self.GROUP_BY_PRODUCT_RADIO)
            return

        raise SantriAutomationError(
            f"Tipo de exportação não suportado: {export_key}"
        )

    def _nearest_combo(
        self,
        relation: HwndWrapper,
        target: tuple[int, int],
    ) -> HwndWrapper:
        root = relation.rectangle()
        candidates: list[tuple[float, HwndWrapper]] = []
        for control in relation.descendants():
            if control.class_name() not in {"TComboBox", "TXComboBox"}:
                continue
            rectangle = control.rectangle()
            if not control.is_visible():
                continue
            center_x = (rectangle.left + rectangle.right) / 2 - root.left
            center_y = (rectangle.top + rectangle.bottom) / 2 - root.top
            distance = (center_x - target[0]) ** 2 + (
                center_y - target[1]
            ) ** 2
            candidates.append((distance, control))

        if not candidates:
            raise SantriAutomationError(
                "O campo Produto sob encomenda não foi encontrado."
            )
        candidates.sort(key=lambda item: item[0])
        distance, combo = candidates[0]
        if distance > 80**2:
            raise SantriAutomationError(
                "A posição do campo Produto sob encomenda mudou no Santri."
            )
        return combo

    @staticmethod
    def _select_combo_text(combo: HwndWrapper, value: str) -> None:
        try:
            combo.select(value)
        except Exception as error:
            items = []
            try:
                items = combo.item_texts()
            except Exception:
                pass
            raise SantriAutomationError(
                f"Não foi possível selecionar '{value}'. Opções: {items}"
            ) from error
        time.sleep(0.3)

    def _wait_for_result(
        self,
        relation: HwndWrapper,
        timeout_seconds: int,
        activate_result_tab: bool = False,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if activate_result_tab:
                try:
                    relation.click_input(coords=self.STOCK_RESULT_TAB)
                except Exception:
                    pass
            if self._result_tab_visible(relation):
                return
            time.sleep(1)
        raise SantriAutomationError(
            "O processamento do relatório excedeu 10 minutos."
        )

    @staticmethod
    def _result_tab_visible(relation: HwndWrapper) -> bool:
        for control in relation.descendants():
            if (
                control.class_name() == "TTabSheet"
                and control.window_text() == "Resultado"
                and control.is_visible()
            ):
                return True
        return False

    def _export_spreadsheet(
        self,
        relation: HwndWrapper,
        destination: Path,
        button_coords: tuple[int, int] | None = None,
        confirm_analytic: bool = False,
        confirm_stock_model: bool = False,
    ) -> None:
        before_handles = {
            window.handle
            for window in Desktop(backend="win32").windows(
                visible_only=True
            )
        }
        relation.click_input(
            coords=button_coords or self.SPREADSHEET_BUTTON
        )
        if confirm_analytic:
            self._confirm_transfer_analytic()
        if confirm_stock_model:
            self._confirm_stock_model()

        deadline = time.monotonic() + 45
        dialog = None
        while time.monotonic() < deadline:
            if destination.exists() and destination.stat().st_size >= 1024:
                self._dismiss_spreadsheet_success(relation)
                return
            for window in Desktop(backend="win32").windows(
                visible_only=True
            ):
                title = window.window_text().lower()
                if (
                    window.handle not in before_handles
                    and (
                        window.class_name() == "#32770"
                        or "salvar" in title
                        or "save" in title
                    )
                ):
                    dialog = window
                    break
            if dialog is not None:
                break
            time.sleep(0.5)

        if dialog is None:
            raise SantriAutomationError(
                "O Santri não abriu a janela para salvar a planilha."
            )

        dialog.set_focus()
        keyboard.send_keys("%n")
        keyboard.send_keys("^a")
        keyboard.send_keys(str(destination), with_spaces=True)
        keyboard.send_keys("{ENTER}")

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if destination.exists() and destination.stat().st_size >= 1024:
                self._dismiss_spreadsheet_success(relation)
                return
            time.sleep(1)
        raise SantriAutomationError(
            f"O arquivo não foi criado em {destination}."
        )

    def _confirm_transfer_analytic(self) -> None:
        selector = Desktop(backend="win32").window(title="Selecionar")
        try:
            selector.wait("exists visible enabled", timeout=15)
        except PywinautoTimeoutError as error:
            raise SantriAutomationError(
                "A seleção Analítico/Sintético não foi aberta."
            ) from error
        dialog = selector.wrapper_object()
        dialog.set_focus()
        dialog.click_input(coords=self.TRANSFER_ANALYTIC_OPTION)
        dialog.click_input(coords=self.TRANSFER_ANALYTIC_OK)
        try:
            selector.wait_not("visible", timeout=10)
        except PywinautoTimeoutError as error:
            raise SantriAutomationError(
                "Não foi possível confirmar o relatório analítico."
            ) from error

    def _confirm_stock_model(self) -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            for window in Desktop(backend="win32").windows(visible_only=True):
                descendants = []
                try:
                    descendants = window.descendants()
                except Exception:
                    continue
                texts = [window.window_text(), *(
                    control.window_text() for control in descendants
                )]
                joined = " ".join(texts).lower()
                if "dados por empresa - modelo 2" not in joined:
                    continue
                window.set_focus()
                option = next(
                    (
                        control
                        for control in descendants
                        if "dados por empresa - modelo 2"
                        in control.window_text().strip().lower()
                    ),
                    None,
                )
                if option is not None:
                    option.click_input()
                for control in descendants:
                    if control.window_text().strip().lower() in {"ok", "&ok"}:
                        control.click_input()
                        return
                keyboard.send_keys("{ENTER}")
                return
            time.sleep(0.3)
        raise SantriAutomationError(
            "A seleção 'Dados por empresa - modelo 2' não foi aberta."
        )

    def _return_to_main(
        self,
        relation: HwndWrapper,
        main: HwndWrapper,
    ) -> None:
        handle = relation.handle
        try:
            relation.close()
            Desktop(backend="win32").window(handle=handle).wait_not(
                "exists visible",
                timeout=10,
            )
        except (Exception, PywinautoTimeoutError) as error:
            raise SantriAutomationError(
                "Não foi possível fechar a tela do relatório no Santri."
            ) from error
        self._ensure_main_maximized(main)
        self.log("Tela do relatório fechada; Santri pronto na tela inicial.")

    def _dismiss_spreadsheet_success(
        self,
        relation: HwndWrapper,
    ) -> None:
        time.sleep(1.2)
        for window in Desktop(backend="win32").windows(visible_only=True):
            try:
                descendants = window.descendants()
            except Exception:
                continue
            joined = " ".join(
                [window.window_text(), *(item.window_text() for item in descendants)]
            ).lower()
            if not any(
                phrase in joined
                for phrase in (
                    "planilha gerada com sucesso",
                    "planilha salva com sucesso",
                )
            ):
                continue
            window.set_focus()
            for control in descendants:
                if control.window_text().strip().lower() in {"ok", "&ok"}:
                    control.click_input()
                    time.sleep(0.4)
                    self.log("Aviso de planilha gerada confirmado.")
                    return
            keyboard.send_keys("{ENTER}")
            time.sleep(0.4)
            if relation.is_enabled():
                self.log("Aviso de planilha gerada confirmado.")
                return
        rectangle = relation.rectangle()
        mouse.click(
            coords=(
                rectangle.left + self.SPREADSHEET_SUCCESS_OK[0],
                rectangle.top + self.SPREADSHEET_SUCCESS_OK[1],
            )
        )

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if relation.is_enabled():
                self.log(
                    "Aviso 'Planilha gerada com sucesso' confirmado."
                )
                return
            time.sleep(0.2)

        keyboard.send_keys("{ENTER}")
        time.sleep(0.5)
        if not relation.is_enabled():
            raise SantriAutomationError(
                "Não foi possível confirmar o aviso de planilha gerada."
            )

    def _company(self, company_key: str) -> CompanyDefinition:
        try:
            return self.config.companies[company_key]
        except KeyError as error:
            raise SantriAutomationError(
                f"Empresa inválida: {company_key}"
            ) from error

    def _exports(
        self,
        export_keys: Iterable[str],
    ) -> tuple[ExportDefinition, ...]:
        selected_keys = set(export_keys)
        selected = tuple(
            export
            for export in self.config.workflow.exports
            if export.key in selected_keys
        )
        if not selected:
            raise SantriAutomationError(
                "Selecione ao menos uma exportação."
            )
        return selected

    @staticmethod
    def _filename(
        company: CompanyDefinition,
        export: ExportDefinition,
        execution_date: date,
        filename_prefix: str | None = None,
    ) -> str:
        prefix = (
            filename_prefix.strip()
            if filename_prefix is not None
            else company.filename_prefix
        )
        if not prefix:
            prefix = company.filename_prefix
        if any(character in prefix for character in '<>:"/\\|?*'):
            raise SantriAutomationError(
                "O prefixo do arquivo contém um caractere inválido."
            )
        return export.filename_template.format(
            company=prefix,
            date=execution_date.strftime("%d-%m-%Y"),
        )

    def _downloads_path(
        self,
        company: CompanyDefinition,
        export: ExportDefinition,
        execution_date: date,
        filename_prefix: str | None = None,
        downloads_root: Path | None = None,
    ) -> Path:
        root = downloads_root or Path.home() / "Downloads"
        return (
            root
            / self._filename(
                company,
                export,
                execution_date,
                filename_prefix,
            )
        )

    def _transfer_downloads_path(
        self,
        company: CompanyDefinition,
        execution_date: date,
        filename_prefix: str | None,
        downloads_root: Path | None,
    ) -> Path:
        root = downloads_root or Path.home() / "Downloads"
        prefix = (
            filename_prefix.strip()
            if filename_prefix is not None
            else company.filename_prefix
        )
        if any(character in prefix for character in '<>:"/\\|?*'):
            raise SantriAutomationError(
                "O prefixo do arquivo contém um caractere inválido."
            )
        original = (
            "Relação de Transferências - Analítico - "
            f"{execution_date.strftime('%d-%m-%Y')}.ods"
        )
        filename = f"{prefix}_{original}" if prefix else original
        return root / filename

    def _stock_downloads_path(
        self,
        company: CompanyDefinition,
        execution_date: date,
        filename_prefix: str | None,
        downloads_root: Path | None,
    ) -> Path:
        root = downloads_root or Path.home() / "Downloads"
        prefix = (
            filename_prefix.strip()
            if filename_prefix is not None
            else company.filename_prefix
        )
        if any(character in prefix for character in '<>:"/\\|?*'):
            raise SantriAutomationError(
                "O prefixo do arquivo contém um caractere inválido."
            )
        original = (
            "Valor do estoque analítico - "
            f"{execution_date.strftime('%d-%m-%Y')}.ods"
        )
        filename = f"{prefix}_{original}" if prefix else original
        return root / filename

    def _prepare_download_destination(
        self,
        destination: Path,
        existing_file_policy: str,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            return
        if existing_file_policy != "replace":
            raise SantriAutomationError(
                f"O arquivo já existe em Downloads: {destination.name}. "
                "Mova ou renomeie o arquivo antes de repetir a exportação."
            )
        if not destination.is_file():
            raise SantriAutomationError(
                f"O destino existente não é um arquivo: {destination}."
            )
        destination.unlink()
        self.log(f"Arquivo anterior apagado: {destination.name}.")

    def _network_path(
        self,
        company: CompanyDefinition,
        export: ExportDefinition,
        execution_date: date,
        filename_prefix: str | None = None,
        destination_root: Path | None = None,
    ) -> Path:
        root = destination_root or company.network_root
        return (
            root
            / export.destination_subfolder
            / self._filename(
                company,
                export,
                execution_date,
                filename_prefix,
            )
        )
