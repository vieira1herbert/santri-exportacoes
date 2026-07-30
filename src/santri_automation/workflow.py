from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .config import AutomationConfig, CompanyDefinition, ExportDefinition


@dataclass(frozen=True)
class Step:
    action: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionPlan:
    action: str
    company: CompanyDefinition
    steps: tuple[Step, ...]
    expected_files: tuple[Path, ...]


def _file_paths(
    export: ExportDefinition,
    company: CompanyDefinition,
    execution_date: date,
) -> tuple[Path, Path]:
    filename = export.filename_template.format(
        company=company.filename_prefix,
        date=execution_date.strftime("%d-%m-%Y"),
    )
    staging_file = Path.home() / "Downloads" / filename
    destination_file = (
        company.network_root / export.destination_subfolder / filename
    )
    return staging_file, destination_file


def _santri_export_steps(
    export: ExportDefinition,
    company: CompanyDefinition,
    execution_date: date,
) -> tuple[list[Step], Path]:
    staging_file, _ = _file_paths(export, company, execution_date)
    steps: list[Step] = [
        Step(
            action="begin_export",
            description=f"Preparar {export.name}",
            parameters={"export_key": export.key},
        )
    ]
    for rule in export.filters:
        steps.extend(
            [
                Step(
                    action="open_tab",
                    description=f"Abrir a aba {rule.tab}",
                    parameters={"tab": rule.tab},
                ),
                Step(
                    action=f"set_{rule.control}",
                    description=f"Definir {rule.field} = {rule.value}",
                    parameters={
                        "field": rule.field,
                        "value": rule.value,
                    },
                ),
            ]
        )
    steps.extend(
        [
            Step(
                action="click_process",
                description="Processar a Relação de Produtos",
            ),
            Step(
                action="wait_processing",
                description="Aguardar o Santri concluir o processamento",
                parameters={"timeout_seconds": 600},
            ),
            Step(
                action="click_spreadsheet",
                description="Clicar em Planilha",
            ),
            Step(
                action="save_file",
                description=f"Salvar {staging_file.name} em Downloads",
                parameters={"path": str(staging_file)},
            ),
            Step(
                action="validate_file",
                description="Validar que o arquivo ODS foi gerado",
                parameters={"path": str(staging_file), "minimum_bytes": 1024},
            ),
        ]
    )
    return steps, staging_file


def build_export_plan(
    config: AutomationConfig,
    company_key: str,
    execution_date: date | None = None,
) -> ExecutionPlan:
    company = _get_company(config, company_key)
    current_date = execution_date or date.today()
    steps: list[Step] = [
        Step(
            action="launch_application",
            description=f"Abrir o Santri da {company.label}",
            parameters={"shortcut": str(company.shortcut)},
        ),
        Step(
            action="login",
            description=f"Realizar login seguro na {company.label}",
            parameters={"credential_target": company.credential_target},
        ),
        Step(
            action="open_menu_path",
            description="Abrir Relatórios > Produtos > Produtos",
            parameters={"items": list(config.workflow.menu_path)},
        ),
        Step(
            action="wait_window",
            description="Aguardar a janela Relação de Produtos",
            parameters={
                "title_contains": config.workflow.window_title_contains,
                "timeout_seconds": 60,
            },
        ),
    ]
    expected_files: list[Path] = []

    for export in config.workflow.exports:
        export_steps, staging_file = _santri_export_steps(
            export=export,
            company=company,
            execution_date=current_date,
        )
        steps.extend(export_steps)
        expected_files.append(staging_file)

    return ExecutionPlan(
        action="export",
        company=company,
        steps=tuple(steps),
        expected_files=tuple(expected_files),
    )


def build_redirect_plan(
    config: AutomationConfig,
    company_key: str,
    execution_date: date | None = None,
) -> ExecutionPlan:
    company = _get_company(config, company_key)
    current_date = execution_date or date.today()
    steps: list[Step] = []
    expected_files: list[Path] = []

    for export in config.workflow.exports:
        staging_file, destination_file = _file_paths(
            export=export,
            company=company,
            execution_date=current_date,
        )
        steps.extend(
            [
                Step(
                    action="locate_file",
                    description=f"Localizar {staging_file.name} em Downloads",
                    parameters={"path": str(staging_file)},
                ),
                Step(
                    action="validate_file",
                    description="Validar o arquivo antes de redirecionar",
                    parameters={
                        "path": str(staging_file),
                        "minimum_bytes": 1024,
                    },
                ),
                Step(
                    action="move_file",
                    description=(
                        f"Redirecionar para {export.destination_subfolder}"
                    ),
                    parameters={
                        "source": str(staging_file),
                        "destination": str(destination_file),
                    },
                ),
            ]
        )
        expected_files.append(destination_file)

    steps.append(
        Step(
            action="postprocess",
            description="Executar conversão ODS para XLSX e atualizar o Power Query",
            parameters={
                "command": company.postprocess_command,
                "network_root": str(company.network_root),
            },
        )
    )
    return ExecutionPlan(
        action="redirect",
        company=company,
        steps=tuple(steps),
        expected_files=tuple(expected_files),
    )


def build_cadastro_produtos_plan(
    config: AutomationConfig,
    company_key: str,
    execution_date: date | None = None,
) -> ExecutionPlan:
    export_plan = build_export_plan(config, company_key, execution_date)
    redirect_plan = build_redirect_plan(config, company_key, execution_date)
    return ExecutionPlan(
        action="combined",
        company=export_plan.company,
        steps=export_plan.steps + redirect_plan.steps,
        expected_files=redirect_plan.expected_files,
    )


def _get_company(
    config: AutomationConfig,
    company_key: str,
) -> CompanyDefinition:
    if company_key not in config.companies:
        valid = ", ".join(sorted(config.companies))
        raise ValueError(f"Empresa inválida: {company_key}. Use: {valid}")
    return config.companies[company_key]
