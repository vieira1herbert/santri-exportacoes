from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .date_ranges import resolve_date_range
from .windows_driver import SantriAutomationError


@dataclass(frozen=True)
class ExecutionContext:
    company_key: str
    filename_prefix: str
    destination: Path | None
    downloads_root: Path
    backup_root: Path
    existing_file_policy: str
    timeout_seconds: int
    date_range: dict[str, str] | None = None
    include_asset_consumption: bool = False
    workflow_id: str = ""
    step_runner: (
        Callable[[str, Callable[[], tuple[Path, ...]]], tuple[Path, ...]] | None
    ) = None

    def run_step(
        self,
        name: str,
        operation: Callable[[], tuple[Path, ...]],
    ) -> tuple[Path, ...]:
        if self.step_runner is None:
            return operation()
        return self.step_runner(name, operation)


class WorkflowExecutor(Protocol):
    workflow_id: str

    def execute(
        self,
        action: str,
        driver: Any,
        context: ExecutionContext,
    ) -> tuple[Path, ...]: ...


class CadastroProdutosExecutor:
    workflow_id = "cadastro_produtos"
    export_keys = ("sob_encomenda", "completo")

    def execute(
        self,
        action: str,
        driver: Any,
        context: ExecutionContext,
    ) -> tuple[Path, ...]:
        if action in {"redirect", "update", "all"} and context.destination is None:
            raise SantriAutomationError(
                "Configure a pasta de destino desta exportação."
            )
        if action == "export":
            return context.run_step(
                "Exportar Cadastro de Produtos",
                lambda: driver.export(
                    context.company_key,
                    self.export_keys,
                    filename_prefix=context.filename_prefix,
                    downloads_root=context.downloads_root,
                    existing_file_policy=context.existing_file_policy,
                    timeout_seconds=context.timeout_seconds,
                ),
            )
        if action == "redirect":
            return context.run_step(
                "Redirecionar Cadastro de Produtos",
                lambda: driver.redirect(
                    context.company_key,
                    self.export_keys,
                    filename_prefix=context.filename_prefix,
                    destination_root=context.destination,
                    downloads_root=context.downloads_root,
                    backup_root=context.backup_root,
                ),
            )
        if action == "update":
            return context.run_step(
                "Atualizar Base de Cadastro de Produtos",
                lambda: (
                    driver.update_base(
                        context.company_key,
                        destination_root=context.destination,
                        timeout_seconds=context.timeout_seconds,
                    ),
                ),
            )
        if action != "all":
            raise SantriAutomationError(f"Ação não suportada: {action}")

        self._log(driver, "Etapa 1 de 3: exportando pelo Santri.")
        exported = self.execute("export", driver, context)
        self._log(driver, "Etapa 2 de 3: redirecionando arquivos.")
        redirected = self.execute("redirect", driver, context)
        self._log(driver, "Etapa 3 de 3: atualizando a base.")
        updated = self.execute("update", driver, context)
        return (*exported, *redirected, *updated)

    @staticmethod
    def _log(driver: Any, message: str) -> None:
        callback = getattr(driver, "log", None) or getattr(driver, "logger", None)
        if callable(callback):
            callback(message)


class TransferenciasExecutor:
    workflow_id = "transfer_ncias"

    def execute(
        self,
        action: str,
        driver: Any,
        context: ExecutionContext,
    ) -> tuple[Path, ...]:
        if action in {"redirect", "update", "all"} and context.destination is None:
            raise SantriAutomationError(
                "Configure a pasta de destino desta exportação."
            )
        start_date, end_date = resolve_date_range(context.date_range)
        if action == "export":
            return context.run_step(
                "Exportar Transferências",
                lambda: driver.export_transferencias(
                    context.company_key,
                    start_date=start_date,
                    end_date=end_date,
                    filename_prefix=context.filename_prefix,
                    downloads_root=context.downloads_root,
                    existing_file_policy=context.existing_file_policy,
                    timeout_seconds=context.timeout_seconds,
                ),
            )
        if action == "redirect":
            return context.run_step(
                "Redirecionar Transferências",
                lambda: driver.redirect_transferencias(
                    context.company_key,
                    execution_date=end_date,
                    filename_prefix=context.filename_prefix,
                    destination_root=context.destination,
                    downloads_root=context.downloads_root,
                    backup_root=context.backup_root,
                ),
            )
        if action == "update":
            return context.run_step(
                "Atualizar Base de Transferências",
                lambda: (
                    driver.update_transferencias(
                        context.company_key,
                        destination_root=context.destination,
                        timeout_seconds=context.timeout_seconds,
                    ),
                ),
            )
        if action != "all":
            raise SantriAutomationError(f"Ação não suportada: {action}")
        self._log(driver, "Etapa 1 de 3: exportando Transferências pelo Santri.")
        exported = self.execute("export", driver, context)
        self._log(driver, "Etapa 2 de 3: redirecionando a planilha.")
        redirected = self.execute("redirect", driver, context)
        self._log(driver, "Etapa 3 de 3: convertendo e atualizando a base.")
        updated = self.execute("update", driver, context)
        return (*exported, *redirected, *updated)

    @staticmethod
    def _log(driver: Any, message: str) -> None:
        callback = getattr(driver, "log", None) or getattr(driver, "logger", None)
        if callable(callback):
            callback(message)


class EstoqueDisponivelExecutor:
    workflow_id = "estoque_disponivel"

    def execute(
        self,
        action: str,
        driver: Any,
        context: ExecutionContext,
    ) -> tuple[Path, ...]:
        if action in {"redirect", "update", "all"} and context.destination is None:
            raise SantriAutomationError(
                "Configure a pasta mensal de destino desta exportação."
            )
        if action == "export":
            return context.run_step(
                "Exportar Estoque Disponível",
                lambda: driver.export_estoque_disponivel(
                    context.company_key,
                    include_asset_consumption=context.include_asset_consumption,
                    filename_prefix=context.filename_prefix,
                    downloads_root=context.downloads_root,
                    existing_file_policy=context.existing_file_policy,
                    timeout_seconds=context.timeout_seconds,
                ),
            )
        if action == "redirect":
            return context.run_step(
                "Redirecionar Estoque Disponível",
                lambda: driver.redirect_estoque_disponivel(
                    context.company_key,
                    filename_prefix=context.filename_prefix,
                    destination_root=context.destination,
                    downloads_root=context.downloads_root,
                    backup_root=context.backup_root,
                ),
            )
        if action == "update":
            return context.run_step(
                "Atualizar Base de Estoque Disponível",
                lambda: (
                    driver.update_estoque_disponivel(
                        context.company_key,
                        destination_root=context.destination,
                        timeout_seconds=context.timeout_seconds,
                    ),
                ),
            )
        if action != "all":
            raise SantriAutomationError(f"Ação não suportada: {action}")
        self._log(driver, "Etapa 1 de 3: exportando Estoque Disponível pelo Santri.")
        exported = self.execute("export", driver, context)
        self._log(driver, "Etapa 2 de 3: redirecionando a planilha.")
        redirected = self.execute("redirect", driver, context)
        self._log(driver, "Etapa 3 de 3: convertendo e atualizando a base.")
        updated = self.execute("update", driver, context)
        return (*exported, *redirected, *updated)

    @staticmethod
    def _log(driver: Any, message: str) -> None:
        callback = getattr(driver, "log", None) or getattr(driver, "logger", None)
        if callable(callback):
            callback(message)


class ExecutorRegistry:
    def __init__(self, executors: list[WorkflowExecutor]) -> None:
        self._executors = {executor.workflow_id: executor for executor in executors}

    def get(self, workflow_id: str) -> WorkflowExecutor:
        executor = self._executors.get(workflow_id)
        if executor is None:
            raise SantriAutomationError(
                "Esta automação ainda não possui um executor Windows."
            )
        return executor


def build_default_registry() -> ExecutorRegistry:
    return ExecutorRegistry(
        [
            CadastroProdutosExecutor(),
            TransferenciasExecutor(),
            EstoqueDisponivelExecutor(),
        ]
    )
