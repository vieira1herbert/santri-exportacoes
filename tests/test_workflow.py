from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
RESOURCES_ROOT = SOURCE_ROOT / "santri_automation" / "resources"
sys.path.insert(0, str(SOURCE_ROOT))

from santri_automation.config import load_config
from santri_automation.catalog import ExportCatalog
from santri_automation.windows_driver import (
    SantriAutomationError,
    WindowsSantriDriver,
)
from santri_automation.desktop_app import DashboardApi
from santri_automation.workflow import build_export_plan, build_redirect_plan


class CadastroProdutosWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(
            RESOURCES_ROOT / "config" / "cadastro_produtos.json"
        )

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
                reading_folder = (
                    destination_root / export.destination_subfolder
                )
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
            )

            self.assertEqual(2, len(moved))
            self.assertTrue(marker.exists())
            for destination in moved:
                self.assertEqual([destination], list(destination.parent.iterdir()))

    def test_config_contains_no_passwords(self) -> None:
        config_text = (
            RESOURCES_ROOT / "config" / "cadastro_produtos.json"
        ).read_text(encoding="utf-8").lower()
        self.assertNotIn("password", config_text)
        self.assertNotIn("senha", config_text)

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
                self.assertEqual(1, len(workflows))
                cadastro = workflows[0]
                self.assertEqual("cadastro_produtos", cadastro["id"])
                self.assertEqual(
                    ["Base sob encomenda", "Base completa"],
                    cadastro["outputs"],
                )

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
            api = DashboardApi()
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
                calls.append(
                    (company_key, destination_root, timeout_seconds)
                )
                return destination_root / "ShellCadastroProdutos.ps1"

        with tempfile.TemporaryDirectory() as temporary:
            api = DashboardApi()
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
                }
            )
            self.assertEqual("horus", saved["startup_company"])
            self.assertEqual(r"D:\Santri", saved["downloads_folder"])
            self.assertEqual("replace", saved["existing_file_policy"])
            self.assertEqual(15, saved["timeout_minutes"])


if __name__ == "__main__":
    unittest.main()
