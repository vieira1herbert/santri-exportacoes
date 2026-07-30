from __future__ import annotations

import os
import shutil
import subprocess
import time
import zipfile
from collections.abc import Callable, Iterable
from datetime import date
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

        return tuple(created)

    def redirect(
        self,
        company_key: str,
        export_keys: Iterable[str],
        execution_date: date | None = None,
        filename_prefix: str | None = None,
        destination_root: Path | None = None,
        downloads_root: Path | None = None,
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

        for folder in {destination.parent for _, destination in prepared}:
            self._clear_destination_folder(folder, root)

        for source, destination in prepared:
            self.log(f"Redirecionando {source.name}...")
            shutil.move(str(source), str(destination))
            moved.append(destination)
            self.log(f"Arquivo enviado para: {destination.parent}")

        self.log(
            "Redirecionamento concluído. Use “Atualizar Base” para converter "
            "os arquivos e atualizar o Power Query."
        )
        return tuple(moved)

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

        escaped_script = str(script).replace("'", "''")
        command = (
            "Remove-Item Alias:pause -ErrorAction SilentlyContinue; "
            "function global:pause {}; "
            f"& '{escaped_script}'"
        )
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
        if main.is_minimized():
            main.restore()
        main.set_focus()
        return main

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
        relation.set_focus()
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
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
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
    ) -> None:
        before_handles = {
            window.handle
            for window in Desktop(backend="win32").windows(
                visible_only=True
            )
        }
        relation.click_input(coords=self.SPREADSHEET_BUTTON)

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

    def _dismiss_spreadsheet_success(
        self,
        relation: HwndWrapper,
    ) -> None:
        time.sleep(1.2)
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
