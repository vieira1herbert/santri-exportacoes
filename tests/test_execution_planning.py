from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

from santri_automation.services.execution_planning import ExecutionRequestPlanner
from santri_automation.windows_driver import SantriAutomationError


class ExecutionRequestPlannerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = ExecutionRequestPlanner()
        self.catalog = {
            "settings": {
                "downloads_folder": r"C:\Downloads",
                "existing_file_policy": "replace",
                "timeout_minutes": 10,
            },
            "companies": {
                "sol": {
                    "folder": r"S:\SOL",
                    "workflows": [
                        {
                            "id": "cadastro_produtos",
                            "name": "Cadastro de Produtos",
                            "schedule": {"max_attempts": 3},
                        }
                    ],
                }
            },
        }

    def test_prepares_operational_settings_without_mutating_catalog(self) -> None:
        request = self.planner.prepare(
            self.catalog,
            "sol",
            ["cadastro_produtos"],
            "all",
        )
        self.assertEqual(Path(r"C:\Downloads"), request.downloads_root)
        self.assertEqual("replace", request.existing_file_policy)
        self.assertEqual(600, request.timeout_seconds)
        self.assertFalse(request.uses_temporary_options)
        self.assertIsNot(
            request.workflows[0], self.catalog["companies"]["sol"]["workflows"][0]
        )

    def test_applies_bounded_temporary_options_to_request_only(self) -> None:
        request = self.planner.prepare(
            self.catalog,
            "sol",
            ["cadastro_produtos"],
            "export",
            {
                "destination": r"S:\SOL\Temporario",
                "filename_prefix": "Teste",
                "timeout_minutes": 90,
                "max_attempts": 9,
            },
        )
        workflow = request.workflows[0]
        self.assertEqual("Teste", workflow["filename_prefix"])
        self.assertEqual(3600, request.timeout_seconds)
        self.assertEqual(5, workflow["schedule"]["max_attempts"])
        self.assertNotIn(
            "filename_prefix",
            self.catalog["companies"]["sol"]["workflows"][0],
        )

    def test_rejects_destination_outside_company_scope(self) -> None:
        with self.assertRaisesRegex(SantriAutomationError, "pasta da empresa"):
            self.planner.prepare(
                self.catalog,
                "sol",
                ["cadastro_produtos"],
                "export",
                {"destination": r"C:\Fora"},
            )

    def test_rejects_unknown_action_and_workflow(self) -> None:
        with self.assertRaisesRegex(SantriAutomationError, "Ação inválida"):
            self.planner.prepare(
                self.catalog,
                "sol",
                ["cadastro_produtos"],
                "delete",
            )
        with self.assertRaisesRegex(SantriAutomationError, "não foi encontrada"):
            self.planner.prepare(
                self.catalog,
                "sol",
                ["inexistente"],
                "export",
            )

    def test_rejects_non_numeric_operational_limits(self) -> None:
        with self.assertRaisesRegex(SantriAutomationError, "Tempo limite inválido"):
            self.planner.prepare(
                self.catalog,
                "sol",
                ["cadastro_produtos"],
                "export",
                {"timeout_minutes": "indefinido"},
            )


if __name__ == "__main__":
    unittest.main()
