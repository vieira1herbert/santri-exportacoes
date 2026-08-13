from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
RESOURCES_ROOT = SOURCE_ROOT / "santri_automation" / "resources"
sys.path.insert(0, str(SOURCE_ROOT))


def ui_source() -> str:
    ui_root = RESOURCES_ROOT / "ui"
    paths = [ui_root / "dashboard.html"]
    paths.extend(sorted((ui_root / "styles").glob("*.css")))
    paths.extend(sorted((ui_root / "scripts").rglob("*.js")))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def successful_preflight(*_args):
    return {"ready": True, "failed": 0, "checks": []}


from santri_automation.catalog import ExportCatalog
from santri_automation.config import load_config
from santri_automation.date_ranges import normalize_date_range, resolve_date_range
from santri_automation.desktop_app import DashboardApi
from santri_automation.executors import (
    EstoqueDisponivelExecutor,
    ExecutionContext,
    TransferenciasExecutor,
)
from santri_automation.reliability import (
    ExecutionSession,
    NotificationCenter,
    ReliabilityCenter,
)
from santri_automation.scheduler import (
    WorkflowScheduler,
    format_schedule,
    normalize_schedule,
)
from santri_automation.single_instance import SingleInstance
from santri_automation.windows_driver import (
    SantriAutomationError,
    WindowsSantriDriver,
)
from santri_automation.workflow import build_export_plan, build_redirect_plan


class CadastroProdutosWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(RESOURCES_ROOT / "config" / "cadastro_produtos.json")

    def test_both_companies_have_two_exports(self) -> None:
        for company_key in ("sol", "horus"):
            export_plan = build_export_plan(
                self.config,
                company_key,
                date(2026, 7, 29),
            )
            redirect_plan = build_redirect_plan(
                self.config,
                company_key,
                date(2026, 7, 29),
            )
            self.assertEqual(2, len(export_plan.expected_files))
            self.assertEqual(2, len(redirect_plan.expected_files))
            filenames = [path.name for path in export_plan.expected_files]
            self.assertTrue(any("SOBENCOMENDA" in name for name in filenames))
            self.assertTrue(any("COMPLETO" in name for name in filenames))

    def test_complete_resets_sob_encomenda_before_grouping(self) -> None:
        plan = build_export_plan(
            self.config,
            "sol",
            date(2026, 7, 29),
        )
        complete_start = next(
            index
            for index, step in enumerate(plan.steps)
            if step.action == "begin_export"
            and step.parameters["export_key"] == "completo"
        )
        complete_steps = plan.steps[complete_start:]
        reset_index = next(
            index
            for index, step in enumerate(complete_steps)
            if step.action == "set_select"
            and step.parameters
            == {
                "field": "Produto sob encomenda",
                "value": "Não filtrar",
            }
        )
        grouping_index = next(
            index
            for index, step in enumerate(complete_steps)
            if step.action == "set_radio"
            and step.parameters
            == {
                "field": "Tipo de agrupamento",
                "value": "Grupo de prod.",
            }
        )
        self.assertLess(reset_index, grouping_index)

    def test_export_and_redirect_are_independent(self) -> None:
        export_plan = build_export_plan(
            self.config,
            "sol",
            date(2026, 7, 29),
        )
        redirect_plan = build_redirect_plan(
            self.config,
            "sol",
            date(2026, 7, 29),
        )
        export_actions = {step.action for step in export_plan.steps}
        redirect_actions = {step.action for step in redirect_plan.steps}

        self.assertIn("launch_application", export_actions)
        self.assertIn("click_process", export_actions)
        self.assertNotIn("move_file", export_actions)
        self.assertNotIn("postprocess", export_actions)

        self.assertIn("move_file", redirect_actions)
        self.assertIn("postprocess", redirect_actions)
        self.assertNotIn("launch_application", redirect_actions)
        self.assertNotIn("click_process", redirect_actions)

    def test_redirect_clears_only_the_two_reading_folders(self) -> None:
        execution_date = date(2026, 7, 29)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            downloads = root / "downloads"
            destination_root = root / "Cadastro de Produtos"
            backup_root = root / "backups"
            downloads.mkdir()
            destination_root.mkdir()
            company = replace(
                self.config.companies["sol"],
                network_root=destination_root,
            )
            config = replace(
                self.config,
                companies={**self.config.companies, "sol": company},
            )
            driver = WindowsSantriDriver(config)
            marker = destination_root / "ShellCadastroProdutos.ps1"
            marker.write_text("preservar", encoding="utf-8")

            for export in self.config.workflow.exports:
                source = downloads / driver._filename(
                    company,
                    export,
                    execution_date,
                    "Sol",
                )
                with zipfile.ZipFile(source, "w") as archive:
                    archive.writestr(
                        "mimetype",
                        "application/vnd.oasis.opendocument.spreadsheet",
                    )
                    archive.writestr("content.xml", "novo" * 1024)
                reading_folder = destination_root / export.destination_subfolder
                nested = reading_folder / "antigos"
                nested.mkdir(parents=True)
                (reading_folder / "arquivo_antigo.xlsx").write_bytes(b"antigo")
                (nested / "temporario.txt").write_text(
                    "remover",
                    encoding="utf-8",
                )

            moved = driver.redirect(
                "sol",
                ("sob_encomenda", "completo"),
                execution_date=execution_date,
                filename_prefix="Sol",
                destination_root=destination_root,
                downloads_root=downloads,
                backup_root=backup_root,
            )

            self.assertEqual(2, len(moved))
            self.assertTrue(marker.exists())
            for destination in moved:
                self.assertEqual([destination], list(destination.parent.iterdir()))
            backups = list((backup_root / "sol").glob("*"))
            self.assertEqual(1, len(backups))
            self.assertTrue(
                any(
                    path.name == "arquivo_antigo.xlsx" for path in backups[0].rglob("*")
                )
            )

    def test_config_contains_no_passwords(self) -> None:
        config_text = (
            (RESOURCES_ROOT / "config" / "cadastro_produtos.json")
            .read_text(encoding="utf-8")
            .lower()
        )
        self.assertNotIn("password", config_text)
        self.assertNotIn("senha", config_text)

    def test_redirect_restores_previous_files_when_commit_fails(self) -> None:
        execution_date = date(2026, 7, 29)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            downloads = root / "downloads"
            destination_root = root / "Cadastro de Produtos"
            downloads.mkdir()
            destination_root.mkdir()
            company = replace(
                self.config.companies["sol"],
                network_root=destination_root,
            )
            config = replace(
                self.config,
                companies={**self.config.companies, "sol": company},
            )
            driver = WindowsSantriDriver(config)
            old_files: list[Path] = []
            for export in self.config.workflow.exports:
                source = downloads / driver._filename(
                    company,
                    export,
                    execution_date,
                    "Sol",
                )
                with zipfile.ZipFile(source, "w") as archive:
                    archive.writestr(
                        "mimetype",
                        "application/vnd.oasis.opendocument.spreadsheet",
                    )
                    archive.writestr("content.xml", "novo" * 1024)
                reading_folder = destination_root / export.destination_subfolder
                reading_folder.mkdir()
                old_file = reading_folder / "anterior.txt"
                old_file.write_text("preservar", encoding="utf-8")
                old_files.append(old_file)

            original_copy = shutil.copy2
            final_copies = 0

            def failing_copy(source, destination, *args, **kwargs):
                nonlocal final_copies
                destination_path = Path(destination)
                if destination_path.parent.parent == destination_root:
                    final_copies += 1
                    if final_copies == 2:
                        raise OSError("falha simulada")
                return original_copy(source, destination, *args, **kwargs)

            with (
                patch(
                    "santri_automation.windows_driver.shutil.copy2",
                    side_effect=failing_copy,
                ),
                self.assertRaisesRegex(SantriAutomationError, "restaurados"),
            ):
                driver.redirect(
                    "sol",
                    ("sob_encomenda", "completo"),
                    execution_date=execution_date,
                    filename_prefix="Sol",
                    destination_root=destination_root,
                    downloads_root=downloads,
                    backup_root=root / "backups",
                )

            self.assertTrue(
                all(
                    path.read_text(encoding="utf-8") == "preservar"
                    for path in old_files
                )
            )
            self.assertEqual(2, len(list(downloads.glob("*.ods"))))

    def test_destination_outside_company_root_is_blocked(self) -> None:
        company = self.config.companies["sol"]
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(SantriAutomationError):
                WindowsSantriDriver._validate_company_root(
                    company,
                    Path(temporary),
                )

    def test_invalid_ods_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalido.ods"
            path.write_bytes(b"invalido" * 1024)
            with self.assertRaises(SantriAutomationError):
                WindowsSantriDriver._validate_ods_file(path)

    def test_catalog_treats_cadastro_as_one_complete_workflow(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            state = catalog.load()
            for company_key in ("sol", "horus"):
                workflows = state["companies"][company_key]["workflows"]
                self.assertEqual(3, len(workflows))
                cadastro = next(
                    item for item in workflows if item["id"] == "cadastro_produtos"
                )
                self.assertEqual("cadastro_produtos", cadastro["id"])
                self.assertEqual(
                    ["Base sob encomenda", "Base completa"],
                    cadastro["outputs"],
                )
                estoque = next(
                    item for item in workflows if item["id"] == "estoque_disponivel"
                )
                self.assertTrue(estoque["include_asset_consumption"])
                self.assertIn("Gestao de Estoque Disponivel", estoque["destination"])

    def test_destination_and_filename_prefix_are_configurable(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            saved = catalog.upsert_workflow(
                "sol",
                {
                    "id": "cadastro_produtos",
                    "destination": r"D:\Exportacoes\Produtos",
                    "filename_prefix": "SOL_TESTE",
                    "schedule": "Manual",
                },
            )
            self.assertEqual(
                r"D:\Exportacoes\Produtos",
                saved["destination"],
            )
            self.assertEqual("SOL_TESTE", saved["filename_prefix"])

            filename = WindowsSantriDriver._filename(
                self.config.companies["sol"],
                self.config.workflow.exports[0],
                date(2026, 7, 29),
                "SOL_TESTE",
            )
            self.assertTrue(filename.startswith("SOL_TESTE_"))

    def test_implemented_workflow_saves_description_and_schedule(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        schedule = {
            "enabled": True,
            "entries": [
                {"weekday": 0, "time": "06:30"},
                {"weekday": 2, "time": "07:15"},
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            saved = catalog.upsert_workflow(
                "sol",
                {
                    "id": "cadastro_produtos",
                    "description": "Descrição alterada",
                    "schedule": schedule,
                },
            )
            reloaded = catalog.load()["companies"]["sol"]["workflows"][0]

        self.assertEqual("Descrição alterada", saved["description"])
        self.assertEqual(schedule, reloaded["schedule"])
        self.assertEqual("Seg 06:30 · Qua 07:15", format_schedule(schedule))

    def test_schedule_can_be_turned_off(self) -> None:
        schedule = normalize_schedule(
            {"enabled": False, "entries": [{"weekday": 0, "time": "08:00"}]},
            strict=True,
        )
        self.assertFalse(schedule["enabled"])
        self.assertEqual("Desligado", format_schedule(schedule))

    def test_scheduler_runs_complete_workflow_once_per_slot(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        calls: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            catalog.upsert_workflow(
                "sol",
                {
                    "id": "cadastro_produtos",
                    "schedule": {
                        "enabled": True,
                        "entries": [{"weekday": 0, "time": "06:30"}],
                    },
                },
            )
            scheduler = WorkflowScheduler(
                catalog,
                lambda company, workflow: (
                    calls.append((company, workflow)) or {"ok": True}
                ),
            )
            moment = datetime(2026, 8, 3, 7, 10)
            scheduler.run_pending(moment)
            scheduler.run_pending(moment)

            restarted_scheduler = WorkflowScheduler(
                catalog,
                lambda company, workflow: (
                    calls.append((company, workflow)) or {"ok": True}
                ),
            )
            restarted_scheduler.run_pending(moment)

        self.assertEqual([("sol", "cadastro_produtos")], calls)

    def test_dashboard_always_runs_both_cadastro_outputs(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        calls: list[tuple[str, tuple[str, ...], str]] = []

        class FakeDriver:
            def __init__(self, _config, logger=None) -> None:
                self.logger = logger

            def export(
                self,
                company_key,
                export_keys,
                execution_date=None,
                filename_prefix=None,
                **_kwargs,
            ):
                calls.append(
                    (
                        company_key,
                        tuple(export_keys),
                        filename_prefix,
                    )
                )
                return (
                    Path("sob_encomenda.ods"),
                    Path("completo.ods"),
                )

        with tempfile.TemporaryDirectory() as temporary:
            api = DashboardApi(preflight_validator=successful_preflight)
            api.catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            with (
                patch(
                    "santri_automation.desktop_app.WindowsSantriDriver",
                    FakeDriver,
                ),
                patch(
                    "santri_automation.desktop_app.load_config",
                    return_value=object(),
                ),
            ):
                result = api.run_workflows(
                    "sol",
                    ["cadastro_produtos"],
                    "export",
                )

        self.assertTrue(result["ok"])
        self.assertEqual(
            [
                (
                    "sol",
                    ("sob_encomenda", "completo"),
                    "Sol",
                )
            ],
            calls,
        )

    def test_dashboard_runs_update_base_for_selected_workflow(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        calls: list[tuple[str, Path, int]] = []

        class FakeDriver:
            def __init__(self, _config, logger=None) -> None:
                self.logger = logger

            def update_base(
                self,
                company_key,
                destination_root,
                timeout_seconds,
            ):
                calls.append((company_key, destination_root, timeout_seconds))
                return destination_root / "ShellCadastroProdutos.ps1"

        with tempfile.TemporaryDirectory() as temporary:
            api = DashboardApi(preflight_validator=successful_preflight)
            api.catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            with (
                patch(
                    "santri_automation.desktop_app.WindowsSantriDriver",
                    FakeDriver,
                ),
                patch(
                    "santri_automation.desktop_app.load_config",
                    return_value=object(),
                ),
            ):
                result = api.run_workflows(
                    "sol",
                    ["cadastro_produtos"],
                    "update",
                )

        self.assertTrue(result["ok"])
        self.assertEqual("sol", calls[0][0])
        self.assertEqual(
            Path(r"S:\00. Procurement\SOL\Cadastro de Produtos"),
            calls[0][1],
        )
        self.assertEqual(600, calls[0][2])

    def test_dashboard_runs_all_steps_in_order(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        calls: list[str] = []

        class FakeDriver:
            def __init__(self, _config, logger=None) -> None:
                self.logger = logger

            def export(self, *_args, **_kwargs):
                calls.append("export")
                return (Path("sob.ods"), Path("completo.ods"))

            def redirect(self, *_args, **_kwargs):
                calls.append("redirect")
                return (Path("destino-sob.ods"), Path("destino-completo.ods"))

            def update_base(self, *_args, **_kwargs):
                calls.append("update")
                return Path("ShellCadastroProdutos.ps1")

        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            api = DashboardApi(
                catalog=catalog,
                driver_factory=FakeDriver,
                config_loader=lambda _path: object(),
                preflight_validator=successful_preflight,
            )
            result = api.run_workflows(
                "sol",
                ["cadastro_produtos"],
                "all",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(["export", "redirect", "update"], calls)
        self.assertIn("completo", result["message"])

    def test_dashboard_exposes_run_all_button(self) -> None:
        dashboard = ui_source()
        self.assertIn('data-action="all"', dashboard)
        self.assertIn("Executar tudo", dashboard)

    def test_v16_manual_temporary_parameters_are_explicit_and_not_saved(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        calls: list[str] = []

        class FakeDriver:
            def __init__(self, _config, logger=None) -> None:
                self.logger = logger

            def export(self, _company, _keys, **kwargs):
                calls.append(kwargs["filename_prefix"])
                return (Path("sob.ods"), Path("completo.ods"))

        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(catalog_path, Path(temporary) / "catalog.json")
            original = next(
                item
                for item in catalog.load()["companies"]["sol"]["workflows"]
                if item["id"] == "cadastro_produtos"
            )["filename_prefix"]
            api = DashboardApi(
                catalog=catalog,
                driver_factory=FakeDriver,
                config_loader=lambda _path: object(),
                preflight_validator=successful_preflight,
            )
            result = api.run_workflows(
                "sol",
                ["cadastro_produtos"],
                "export",
                source="manual_temporary",
                temporary_options={"filename_prefix": "TEMP", "max_attempts": 1},
            )
            persisted = next(
                item
                for item in catalog.load()["companies"]["sol"]["workflows"]
                if item["id"] == "cadastro_produtos"
            )["filename_prefix"]

        self.assertTrue(result["ok"])
        self.assertEqual(["TEMP"], calls)
        self.assertEqual(original, persisted)
        self.assertIn("Executar sem salvar", ui_source())

    def test_draft_workflow_can_be_deleted(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            draft = catalog.upsert_workflow(
                "horus",
                {"name": "Transferências", "schedule": "Manual"},
            )
            deleted = catalog.delete_draft_workflow("horus", draft["id"])
            workflows = catalog.load()["companies"]["horus"]["workflows"]

        self.assertEqual(draft["id"], deleted["id"])
        self.assertNotIn(draft["id"], {item["id"] for item in workflows})

    def test_implemented_workflow_cannot_be_deleted(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            with self.assertRaisesRegex(ValueError, "em construção"):
                catalog.delete_draft_workflow("sol", "cadastro_produtos")

    def test_dashboard_exposes_delete_only_for_drafts(self) -> None:
        dashboard = ui_source()
        self.assertIn("delete-report", dashboard)
        self.assertIn("!item.implemented", dashboard)

    def test_dashboard_uses_branded_confirmations(self) -> None:
        dashboard = ui_source()
        self.assertIn('id="confirmation-overlay"', dashboard)
        self.assertIn("function requestConfirmation(options)", dashboard)
        self.assertNotIn("globalThis.confirm", dashboard)
        self.assertNotRegex(dashboard, r"\b(?:confirm|alert|prompt)\s*\(")

    def test_settings_health_badge_keeps_inline_layout(self) -> None:
        dashboard = ui_source()
        self.assertIn(
            ".setting-toggle > span:not(.health-badge):not(.history-status)",
            dashboard,
        )
        self.assertIn(".setting-toggle > .health-badge", dashboard)

    def test_update_base_uses_complete_sync_icon(self) -> None:
        dashboard = ui_source()
        self.assertIn('d="M20 7V3h-4"', dashboard)
        self.assertIn('d="M4 17v4h4"', dashboard)
        self.assertNotIn('d="M20 11a8 8 0 1 0 2 5"', dashboard)

    def test_draft_status_is_compact_and_distinct(self) -> None:
        dashboard = ui_source()
        self.assertIn(".draft-status", dashboard)
        self.assertIn('<span class="draft-status">Em construção</span>', dashboard)
        self.assertIn("align-items: center; justify-content: flex-end", dashboard)

    def test_transfer_date_range_defaults_to_previous_month(self) -> None:
        start, end = resolve_date_range(
            {"mode": "previous_month_to_today"},
            today=date(2026, 8, 3),
        )

        self.assertEqual(date(2026, 7, 1), start)
        self.assertEqual(date(2026, 8, 3), end)

    def test_transfer_custom_date_range_is_persisted(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            saved = catalog.upsert_workflow(
                "horus",
                {
                    "name": "Transferências",
                    "schedule": "Manual",
                    "date_range": {
                        "mode": "custom",
                        "start": "2026-06-01",
                        "end": "2026-08-03",
                    },
                },
            )

        self.assertEqual(
            {
                "mode": "custom",
                "start": "2026-06-01",
                "end": "2026-08-03",
            },
            saved["date_range"],
        )

    def test_transfer_rejects_reversed_date_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "data inicial"):
            normalize_date_range(
                {
                    "mode": "custom",
                    "start": "2026-08-03",
                    "end": "2026-07-01",
                }
            )

    def test_transfer_editor_exposes_automatic_and_custom_periods(self) -> None:
        dashboard = ui_source()
        self.assertIn('id="transfer-date-editor"', dashboard)
        self.assertIn('value="previous_month_to_today"', dashboard)
        self.assertIn('value="custom"', dashboard)
        self.assertIn("function automaticTransferDateRange()", dashboard)

    def test_dashboard_excludes_drafts_from_next_schedule(self) -> None:
        dashboard = ui_source()
        self.assertIn(
            "item.enabled && item.implemented && normalizeSchedule(item.schedule).enabled",
            dashboard,
        )

    def test_dashboard_marks_failure_results_as_warning(self) -> None:
        dashboard = ui_source()
        self.assertIn("function isFailureResult(value)", dashboard)
        self.assertIn("isFailureResult(item.last_result)", dashboard)

    def test_bridge_initialization_is_sequential(self) -> None:
        dashboard = ui_source()
        self.assertIn("async function initializeBridge()", dashboard)
        self.assertIn("await loadState()", dashboard)
        self.assertIn("initializeBridge();", dashboard)
        self.assertNotIn("let bridgeStarted", dashboard)
        self.assertNotIn("bridgePromise", dashboard)
        self.assertIn("window.addEventListener('pywebviewready'", dashboard)
        self.assertIn("globalThis.location.reload()", dashboard)
        self.assertNotIn("Painel disponível em modo de recuperação", dashboard)
        self.assertIn("SOL e HORUS prontas para operar", dashboard)
        self.assertIn("Verificando atalhos, rede, destinos e scripts", dashboard)

    def test_agent_status_reflects_loaded_environment_health(self) -> None:
        dashboard = ui_source()
        self.assertIn("function updateTopbarStatus()", dashboard)
        self.assertIn("session.data.application?.health", dashboard)
        self.assertIn("Agente Windows pronto", dashboard)
        self.assertIn("Ambiente requer atenção", dashboard)
        self.assertIn("status.classList.toggle('warning', !ready)", dashboard)
        self.assertIn("session.data.application?.unread_notifications", dashboard)
        self.assertIn("notificationCount.hidden = unread === 0", dashboard)

    def test_dashboard_operation_status_uses_backend_health_and_history(self) -> None:
        dashboard = ui_source()
        self.assertIn(
            "application?.health?.companies?.[session.activeCompany]?.ready === true",
            dashboard,
        )
        self.assertIn("application?.security?.ready === true", dashboard)
        self.assertIn(
            "const operationReady = companyReady && securityReady && !hasFailure",
            dashboard,
        )
        self.assertIn("const lastExecution = completedHistory[0]", dashboard)
        self.assertIn("formatHistoryTime(lastExecution.timestamp)", dashboard)

    def test_settings_status_labels_use_backend_security_state(self) -> None:
        dashboard = ui_source()
        self.assertIn(
            "security.update_policy === 'restricted_path_and_name'", dashboard
        )
        self.assertIn(
            "security.release?.signed ? 'Assinatura verificada' : 'Release sem assinatura'",
            dashboard,
        )
        self.assertIn(
            "const configuredCompanies = Object.keys(session.data.companies || {}).length",
            dashboard,
        )

    def test_startup_screen_has_corporate_identity_and_live_status(self) -> None:
        dashboard = ui_source()
        self.assertIn("startup-status-panel", dashboard)
        self.assertIn("Idealizado e desenvolvido por Herbert Vieira", dashboard)
        self.assertIn("SOL Atacadista", dashboard)
        self.assertIn("Horus Distribuidora", dashboard)
        self.assertIn("Agente local", dashboard)
        self.assertNotIn("startup-ring", dashboard)

    def test_dashboard_cache_is_invalidated_between_builds(self) -> None:
        desktop = (SOURCE_ROOT / "santri_automation" / "desktop_app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("http_server=True", desktop)
        self.assertIn("private_mode=False", desktop)
        self.assertNotIn("js_api=api", desktop)
        self.assertIn("api.check_for_updates", desktop)
        self.assertIn("api.save_release_preferences", desktop)
        self.assertIn("api.prepare_update", desktop)
        self.assertIn("api.rollback_release", desktop)
        self.assertIn("api.activate_release", desktop)
        self.assertIn("window.expose(", desktop)

    def test_about_page_links_to_the_official_repository(self) -> None:
        dashboard = ui_source()
        self.assertIn("Ver projeto no GitHub", dashboard)
        self.assertIn("api().open_repository()", dashboard)
        self.assertNotIn("Visão geral da arquitetura", dashboard)
        self.assertNotIn("Metodologia de automação", dashboard)

    def test_repository_is_opened_with_a_fixed_url(self) -> None:
        api = DashboardApi()
        with patch("santri_automation.desktop_app.webbrowser.open") as opener:
            opener.return_value = True
            result = api.open_repository()
        opener.assert_called_once_with(
            "https://github.com/vieira1herbert/santri-exportacoes",
            new=2,
        )
        self.assertTrue(result["ok"])

    def test_all_history_states_have_visual_styles(self) -> None:
        dashboard = ui_source()
        self.assertIn(".history-status.blocked", dashboard)
        self.assertIn(".history-status.info", dashboard)
        self.assertIn(".history-table td:first-child", dashboard)

    def test_history_records_workflow_creation_and_deletion(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            api = DashboardApi(catalog=catalog)
            draft = api.save_workflow(
                "horus",
                {
                    "name": "Auditoria de Transferências",
                    "description": "Teste de histórico",
                    "schedule": "Manual",
                },
            )
            api.delete_workflow("horus", draft["id"])
            history = catalog.load()["history"]

        self.assertEqual(
            ["workflow_deleted", "workflow_created"],
            [event["action"] for event in history],
        )
        self.assertTrue(all(event["company"] == "horus" for event in history))

    def test_successful_execution_is_recorded_in_history(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"

        class FakeDriver:
            def __init__(self, _config, logger=None) -> None:
                self.logger = logger

            def export(self, *_args, **_kwargs):
                return (Path("sob.ods"), Path("completo.ods"))

        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            api = DashboardApi(
                catalog=catalog,
                driver_factory=FakeDriver,
                config_loader=lambda _path: object(),
                preflight_validator=successful_preflight,
            )
            result = api.run_workflows(
                "sol",
                ["cadastro_produtos"],
                "export",
            )
            history = catalog.load()["history"]

        self.assertTrue(result["ok"])
        self.assertEqual(["success", "started"], [event["status"] for event in history])
        self.assertEqual(["export", "export"], [event["action"] for event in history])

    def test_dashboard_contains_persistent_history_view(self) -> None:
        dashboard = ui_source()
        self.assertIn("function renderHistory()", dashboard)
        self.assertIn("session.data.history", dashboard)
        self.assertNotIn("histórico detalhado será consolidado", dashboard.lower())

    def test_company_tabs_are_scoped_to_dashboard_page(self) -> None:
        dashboard = ui_source()
        self.assertIn("tabsRoot.hidden = session.activePage !== 'dashboard'", dashboard)
        self.assertIn(
            "renderTabs();\n    router.render(session.activePage);", dashboard
        )
        self.assertIn(".register('dashboard', renderCompany)", dashboard)

    def test_catalog_creates_rotating_backup(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            user_path = Path(temporary) / "catalog.json"
            catalog = ExportCatalog(catalog_path, user_path)
            catalog.save(catalog.load())
            catalog.save_settings({"startup_company": "horus"})
            backups = list((user_path.parent / "backups").glob("*.json"))

        self.assertEqual(1, len(backups))

    def test_only_one_application_instance_acquires_mutex(self) -> None:
        name = f"Local\\SH.SantriExportacoes.Tests.{uuid4().hex}"
        first = SingleInstance(name)
        second = SingleInstance(name)
        try:
            self.assertTrue(first.acquired)
            self.assertFalse(second.acquired)
        finally:
            second.close()
            first.close()

    def test_draft_can_be_replicated_between_companies(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            draft = catalog.upsert_workflow(
                "horus",
                {
                    "name": "Pedidos pendentes",
                    "description": "Base de pedidos pendentes",
                    "destination": r"S:\00. Procurement\HORUS\Pedidos",
                    "filename_prefix": "Horus",
                    "schedule": "Manual",
                },
            )
            replicated = catalog.replicate_draft_workflow(
                "horus",
                "sol",
                draft["id"],
            )

        self.assertEqual("Pedidos pendentes", replicated["name"])
        self.assertEqual("Sol", replicated["filename_prefix"])
        self.assertIn(r"S:\00. Procurement\SOL", replicated["destination"])
        self.assertFalse(replicated["schedule"]["enabled"])

    def test_history_redacts_sensitive_values(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            event = catalog.append_history(
                {
                    "message": "senha=segredo token:abc123",
                    "details": {
                        "password": "segredo",
                        "nested": {"credential_value": "privado"},
                    },
                }
            )

        self.assertNotIn("segredo", str(event))
        self.assertNotIn("abc123", str(event))
        self.assertEqual("[PROTEGIDO]", event["details"]["password"])

    def test_history_can_be_exported_to_csv(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = ExportCatalog(catalog_path, root / "catalog.json")
            catalog.save_settings(
                {
                    "downloads_folder": str(root / "downloads"),
                    "startup_company": "sol",
                }
            )
            catalog.append_history(
                {
                    "company": "sol",
                    "action": "test",
                    "message": "Evento de teste",
                }
            )
            api = DashboardApi(catalog=catalog)
            result = api.export_history_csv()
            exported = Path(result["path"])
            content = exported.read_text(encoding="utf-8-sig")

        self.assertTrue(result["ok"])
        self.assertIn("Evento de teste", content)

    def test_slow_network_path_does_not_block_dashboard(self) -> None:
        class SlowPath:
            @staticmethod
            def exists():
                time.sleep(0.2)
                return True

        started = time.monotonic()
        status = DashboardApi._path_status(SlowPath(), timeout_seconds=0.02)
        elapsed = time.monotonic() - started

        self.assertIsNone(status)
        self.assertLess(elapsed, 0.1)

    def test_general_settings_are_persisted(self) -> None:
        catalog_path = RESOURCES_ROOT / "config" / "export_catalog.json"
        with tempfile.TemporaryDirectory() as temporary:
            catalog = ExportCatalog(
                catalog_path,
                Path(temporary) / "catalog.json",
            )
            saved = catalog.save_settings(
                {
                    "startup_company": "horus",
                    "downloads_folder": r"D:\Santri",
                    "existing_file_policy": "replace",
                    "timeout_minutes": 15,
                    "keep_activity_log": False,
                    "show_success_notification": False,
                    "history_retention_days": 180,
                    "artifact_retention_days": 60,
                    "theme": "dark",
                    "density": "compact",
                    "accent_color": "orange",
                    "reduce_motion": True,
                }
            )
            self.assertEqual("horus", saved["startup_company"])
            self.assertEqual(r"D:\Santri", saved["downloads_folder"])
            self.assertEqual("replace", saved["existing_file_policy"])
            self.assertEqual(15, saved["timeout_minutes"])
            self.assertEqual("dark", saved["theme"])
            self.assertEqual(180, saved["history_retention_days"])
            self.assertEqual(60, saved["artifact_retention_days"])
            self.assertNotIn("density", saved)
            self.assertNotIn("accent_color", saved)
            self.assertNotIn("reduce_motion", saved)

    def test_theme_toggle_and_minimum_window_are_available(self) -> None:
        dashboard = ui_source()
        desktop = (SOURCE_ROOT / "santri_automation" / "desktop_app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('id="setting-theme-toggle"', dashboard)
        self.assertIn("Claro", dashboard)
        self.assertIn("Escuro", dashboard)
        self.assertNotIn('id="setting-density"', dashboard)
        self.assertNotIn('id="setting-accent"', dashboard)
        self.assertNotIn('id="setting-reduce-motion"', dashboard)
        self.assertIn("function applyAppearance(settings = {})", dashboard)
        self.assertIn("*::-webkit-scrollbar", dashboard)
        self.assertIn("min_size=(1180, 720)", desktop)

    def test_settings_page_uses_administrative_information_architecture(self) -> None:
        dashboard = ui_source()
        self.assertIn('class="settings-overview"', dashboard)
        self.assertIn('class="card settings-navigation"', dashboard)
        self.assertIn('data-settings-section="general"', dashboard)
        self.assertIn('data-settings-section="monitoring"', dashboard)
        self.assertIn('data-settings-section="versions"', dashboard)
        self.assertIn('id="settings-save-state"', dashboard)
        self.assertIn('class="settings-company-grid"', dashboard)
        self.assertIn("const markSettingsDirty", dashboard)
        self.assertNotIn('class="identity-grid"', dashboard)

    def test_dark_theme_uses_theme_aware_surfaces(self) -> None:
        dashboard = ui_source()
        self.assertIn("--surface-subtle: #131d25", dashboard)
        self.assertIn("background: var(--surface-subtle)", dashboard)
        self.assertIn("background: var(--surface-info)", dashboard)
        self.assertIn("background: var(--surface-warning)", dashboard)
        self.assertNotIn("background: #fafbfc", dashboard)
        self.assertNotIn("background: #f5faff", dashboard)

    def test_settings_company_brands_keep_contrast_in_both_themes(self) -> None:
        dashboard = ui_source()
        self.assertIn(".settings-hero::after", dashboard)
        self.assertIn("color: #314354", dashboard)
        self.assertIn(
            ".settings-company-status.sol .settings-company-brand img", dashboard
        )
        self.assertIn("invert(36%) sepia(94%)", dashboard)
        self.assertIn('data-theme="dark"] .settings-company-status.sol', dashboard)
        self.assertIn('data-theme="dark"] .settings-company-status.horus', dashboard)
        self.assertIn("brightness(1.55) saturate(1.12)", dashboard)

    def test_workflow_table_wraps_long_content_inside_its_columns(self) -> None:
        dashboard = ui_source()
        self.assertIn(
            "#workflow-table td { min-width: 0; overflow: hidden; }", dashboard
        )
        self.assertIn("#workflow-table .chip { white-space: normal", dashboard)
        self.assertIn("overflow-wrap: anywhere", dashboard)

    def test_custom_scroll_indicator_replaces_native_scrollbars(self) -> None:
        dashboard = ui_source()
        self.assertIn('id="app-scroll-rail"', dashboard)
        self.assertIn('id="app-scroll-progress"', dashboard)
        self.assertIn("function updateScrollIndicator()", dashboard)
        self.assertIn("display: none !important; width: 0 !important", dashboard)
        self.assertIn("linear-gradient(180deg, #00a336", dashboard)

    def test_unsaved_settings_are_confirmed_before_navigation(self) -> None:
        dashboard = ui_source()
        self.assertIn("async function confirmSettingsExit()", dashboard)
        self.assertIn("Deseja salvar as alterações?", dashboard)
        self.assertIn("Continuar sem salvar", dashboard)
        self.assertIn("Salvar alterações", dashboard)
        self.assertIn("if (!await confirmSettingsExit()) return", dashboard)
        self.assertIn("async function confirmEditorExit()", dashboard)
        self.assertIn("async function confirmPendingChanges()", dashboard)
        self.assertIn("Deseja salvar a exportação?", dashboard)
        self.assertIn("editorDirty = true", dashboard)

    def test_workflow_editor_opens_as_a_modal_window(self) -> None:
        dashboard = ui_source()
        self.assertIn('id="editor-overlay"', dashboard)
        self.assertIn('role="dialog" aria-modal="true"', dashboard)
        self.assertIn(".editor.open {", dashboard)
        self.assertIn("position: fixed", dashboard)
        self.assertIn("editorOverlay.hidden = false", dashboard)
        self.assertIn("body.editor-open", dashboard)
        self.assertIn("async function saveWorkflowEditor()", dashboard)

    def test_about_page_shows_authorship_only_in_the_signoff(self) -> None:
        dashboard = ui_source()
        self.assertNotIn('class="about-author"', dashboard)
        self.assertIn('<div class="about-signoff">', dashboard)
        self.assertNotIn(
            "Projeto idealizado e desenvolvido por Herbert Vieira",
            dashboard,
        )

    def test_transfer_executor_uses_configured_period(self) -> None:
        calls = []

        class FakeDriver:
            def export_transferencias(self, company_key, **kwargs):
                calls.append((company_key, kwargs))
                return (Path("transferencias.ods"),)

        context = ExecutionContext(
            company_key="horus",
            filename_prefix="Horus",
            destination=None,
            downloads_root=Path("Downloads"),
            backup_root=Path("Backups"),
            existing_file_policy="replace",
            timeout_seconds=600,
            date_range={
                "mode": "custom",
                "start": "2026-06-01",
                "end": "2026-08-03",
            },
        )
        paths = TransferenciasExecutor().execute(
            "export",
            FakeDriver(),
            context,
        )

        self.assertEqual((Path("transferencias.ods"),), paths)
        self.assertEqual("horus", calls[0][0])
        self.assertEqual(date(2026, 6, 1), calls[0][1]["start_date"])
        self.assertEqual(date(2026, 8, 3), calls[0][1]["end_date"])

    def test_stock_executor_uses_configured_filters(self) -> None:
        calls = []

        class FakeDriver:
            def export_estoque_disponivel(self, company_key, **kwargs):
                calls.append((company_key, kwargs))
                return (Path("estoque.ods"),)

        context = ExecutionContext(
            company_key="sol",
            filename_prefix="SOL",
            destination=None,
            downloads_root=Path("Downloads"),
            backup_root=Path("Backups"),
            existing_file_policy="replace",
            timeout_seconds=600,
            include_asset_consumption=True,
        )
        paths = EstoqueDisponivelExecutor().execute(
            "export",
            FakeDriver(),
            context,
        )

        self.assertEqual((Path("estoque.ods"),), paths)
        self.assertEqual("sol", calls[0][0])
        self.assertTrue(calls[0][1]["include_asset_consumption"])

    def test_stock_filename_preserves_original_name(self) -> None:
        driver = WindowsSantriDriver(self.config)
        path = driver._stock_downloads_path(
            self.config.companies["horus"],
            date(2026, 8, 12),
            "HORUS",
            Path("Downloads"),
        )
        self.assertEqual(
            "HORUS_Valor do estoque analítico - 12-08-2026.ods",
            path.name,
        )

    def test_stock_editor_exposes_monthly_destination_and_filters(self) -> None:
        dashboard = ui_source()
        self.assertIn('id="stock-filter-editor"', dashboard)
        self.assertIn('value="apply"', dashboard)
        self.assertIn('value="skip"', dashboard)
        self.assertIn("PASTA LEITURA - Arquivo ODS para XLXS", dashboard)

    def test_transfer_date_input_starts_at_first_mask_character(self) -> None:
        clicks = []

        class FakeRelation:
            def click_input(self, **kwargs):
                clicks.append(kwargs)

        with (
            patch("santri_automation.windows_driver.keyboard.send_keys") as send_keys,
            patch("santri_automation.windows_driver.time.sleep"),
        ):
            WindowsSantriDriver._set_date_at(
                FakeRelation(),
                (734, 176),
                date(2026, 7, 1),
            )

        self.assertEqual([{"coords": (734, 176)}], clicks)
        self.assertEqual(
            [("{HOME}",), ("01072026",)],
            [call.args for call in send_keys.call_args_list],
        )

    def test_transfer_spreadsheet_confirms_analytic_mode(self) -> None:
        clicks = []

        class FakeDialog:
            def set_focus(self):
                return None

            def click_input(self, **kwargs):
                clicks.append(kwargs)

        class FakeSelector:
            def wait(self, *_args, **_kwargs):
                return None

            def wait_not(self, *_args, **_kwargs):
                return None

            def wrapper_object(self):
                return FakeDialog()

        class FakeDesktop:
            def window(self, **_kwargs):
                return FakeSelector()

        with patch(
            "santri_automation.windows_driver.Desktop",
            return_value=FakeDesktop(),
        ):
            WindowsSantriDriver(self.config)._confirm_transfer_analytic()

        self.assertEqual(
            [{"coords": (25, 75)}, {"coords": (70, 195)}],
            clicks,
        )

    def test_update_scripts_execute_the_original_powershell_file(self) -> None:
        command = WindowsSantriDriver._powershell_file_command(
            Path(r"S:\Base\ShellEstoqueDisp.ps1")
        )

        self.assertEqual("-File", command[-2])
        self.assertEqual(
            r"S:\Base\ShellEstoqueDisp.ps1",
            command[-1],
        )

    def test_completed_export_closes_report_and_restores_main_screen(self) -> None:
        events = []

        class FakeRelation:
            handle = 123

            def close(self):
                events.append("close")

        class FakeMain:
            maximized = False

            def is_minimized(self):
                return False

            def is_maximized(self):
                return self.maximized

            def maximize(self):
                events.append("maximize")
                self.maximized = True

            def set_focus(self):
                events.append("focus")

        class FakeSpec:
            def wait_not(self, *_args, **_kwargs):
                events.append("closed")

        class FakeDesktop:
            def window(self, **_kwargs):
                return FakeSpec()

        with patch(
            "santri_automation.windows_driver.Desktop",
            return_value=FakeDesktop(),
        ):
            WindowsSantriDriver(self.config)._return_to_main(
                FakeRelation(),
                FakeMain(),
            )

        self.assertEqual(
            ["close", "closed", "maximize", "focus"],
            events,
        )

    def test_transfer_filename_preserves_original_name(self) -> None:
        path = WindowsSantriDriver(self.config)._transfer_downloads_path(
            self.config.companies["sol"],
            date(2026, 8, 3),
            "Sol",
            Path("Downloads"),
        )

        self.assertEqual(
            "Sol_Relação de Transferências - Analítico - 03-08-2026.ods",
            path.name,
        )

    def test_v12_notification_center_is_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "notifications.json"
            center = NotificationCenter(path)
            center.add("success", "Concluído", "Base atualizada")
            self.assertEqual(1, len(NotificationCenter(path).list()))
            self.assertEqual(1, center.mark_all_read())
            self.assertTrue(center.list()[0]["read"])
            self.assertEqual(1, center.clear())
            self.assertEqual([], center.list())

    def test_v12_transient_failure_is_retried_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            attempts = []
            session = ExecutionSession(
                Path(temporary),
                "sol",
                ["cadastro_produtos"],
                "all",
                "manual",
                delay=lambda _seconds: None,
            )

            def operation():
                attempts.append(1)
                if len(attempts) < 3:
                    raise SantriAutomationError("Janela não respondeu")
                return (Path("resultado.ods"),)

            result = session.run_step(
                "cadastro_produtos",
                "Exportar",
                operation,
                retries=2,
            )
            report = session.finish("Concluído")

            self.assertEqual(3, len(attempts))
            self.assertEqual((Path("resultado.ods"),), result)
            self.assertTrue(report.exists())
            self.assertTrue(
                any(item["status"] == "retry" for item in session.data["timeline"])
            )

    def test_v12_checkpoint_skips_completed_step_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = ExecutionSession(
                root,
                "horus",
                ["cadastro_produtos"],
                "all",
                "manual",
                delay=lambda _seconds: None,
            )
            first.run_step(
                "cadastro_produtos",
                "Exportar",
                lambda: (Path("arquivo.ods"),),
            )
            first.fail("Falha no redirecionamento")
            resumed = ExecutionSession(
                root,
                "horus",
                ["cadastro_produtos"],
                "all",
                "resume",
                execution_id=first.execution_id,
                delay=lambda _seconds: None,
            )
            called = []
            result = resumed.run_step(
                "cadastro_produtos",
                "Exportar",
                lambda: called.append(True) or (Path("duplicado.ods"),),
            )

            self.assertEqual((), result)
            self.assertEqual([], called)
            self.assertTrue(
                any(item["status"] == "skipped" for item in resumed.data["timeline"])
            )

    def test_v12_checkpoint_can_be_dismissed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            center = ReliabilityCenter(Path(temporary))
            session = center.start_session(
                "sol",
                ["cadastro_produtos"],
                "all",
                "manual",
            )
            session.fail("Interrompida")

            self.assertIsNotNone(center.pending_checkpoint())
            self.assertTrue(center.dismiss_checkpoint(session.execution_id))
            self.assertIsNone(center.pending_checkpoint())

    def test_v12_catalog_backup_can_be_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / "seed.json"
            user = root / "profile" / "catalog.json"
            seed.write_text(
                (RESOURCES_ROOT / "config" / "export_catalog.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            catalog = ExportCatalog(seed, user)
            catalog.save_settings({"startup_company": "sol"})
            backup = catalog.create_manual_backup()
            catalog.save_settings({"startup_company": "horus"})
            catalog.restore_backup(backup["name"])

            self.assertEqual("sol", catalog.load()["settings"]["startup_company"])

    def test_v12_support_package_redacts_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            center = ReliabilityCenter(Path(temporary))
            package = center.create_support_package(
                {
                    "settings": {
                        "password": "segredo",
                        "startup_company": "sol",
                    },
                    "history": [{"message": "token=abc123"}],
                },
                {"ready": True},
                Path(temporary) / "missing.log",
            )
            with zipfile.ZipFile(package) as archive:
                state = json.loads(archive.read("estado-sanitizado.json"))

            self.assertEqual("[PROTEGIDO]", state["settings"]["password"])
            self.assertEqual(
                "token=[PROTEGIDO]",
                state["history"][0]["message"],
            )

    def test_v12_dashboard_exposes_reliability_center(self) -> None:
        dashboard = ui_source()

        self.assertIn("Central de notificações", dashboard)
        self.assertIn("notificationFilter", dashboard)
        self.assertIn("run_diagnostics", dashboard)
        self.assertIn("resume_execution", dashboard)
        self.assertIn("create_catalog_backup", dashboard)

    def test_v15_dashboard_exposes_real_operational_monitoring(self) -> None:
        dashboard = ui_source()
        self.assertIn("MonitoringPresenter", dashboard)
        self.assertIn("Saúde das automações", dashboard)
        self.assertIn("Evolução das execuções", dashboard)
        self.assertIn("Alertas operacionais", dashboard)
        self.assertIn("Desempenho por empresa e exportação", dashboard)
        self.assertIn("copy_operational_summary", dashboard)

    def test_v15_retention_is_configurable_and_persisted(self) -> None:
        dashboard = ui_source()
        self.assertIn('id="setting-history-retention"', dashboard)
        self.assertIn('id="setting-artifact-retention"', dashboard)
        self.assertIn("history_retention_days", dashboard)
        self.assertIn("artifact_retention_days", dashboard)


if __name__ == "__main__":
    unittest.main()
