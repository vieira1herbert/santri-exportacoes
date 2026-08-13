from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from santri_automation.catalog import ExportCatalog
from santri_automation.desktop_app import DashboardApi
from santri_automation.platform import (
    PersistentExecutionQueue,
    WorkflowSimulator,
    WorkflowVersionStore,
    build_blueprint_registry,
)


class WorkflowPlatformV2Test(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = {
            "version": 2,
            "settings": {"downloads_folder": "%USERPROFILE%\\Downloads"},
            "companies": {
                "sol": {
                    "folder": "S:\\00. Procurement\\SOL",
                    "workflows": [
                        {
                            "id": "cadastro_produtos",
                            "name": "Cadastro de Produtos",
                            "destination": "S:\\00. Procurement\\SOL\\Cadastro de Produtos",
                            "filename_prefix": "SOL",
                            "implemented": True,
                            "enabled": True,
                            "lifecycle": "production",
                        }
                    ],
                }
            },
        }

    def test_registered_workflow_simulates_without_windows_interaction(self) -> None:
        result = WorkflowSimulator(build_blueprint_registry()).simulate(
            self.catalog, "sol", "cadastro_produtos", "all"
        )
        self.assertTrue(result["ready"])
        self.assertEqual(
            ["export", "redirect", "update"], [item["key"] for item in result["stages"]]
        )

    def test_simulation_blocks_destination_outside_company_scope(self) -> None:
        self.catalog["companies"]["sol"]["workflows"][0]["destination"] = "C:\\Temp"
        result = WorkflowSimulator(build_blueprint_registry()).simulate(
            self.catalog, "sol", "cadastro_produtos", "all"
        )
        self.assertFalse(result["ready"])
        self.assertIn(
            "destination_scope",
            [item["key"] for item in result["checks"] if item["status"] == "error"],
        )

    def test_workflow_versions_detect_tampering_and_restore_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = WorkflowVersionStore(Path(temporary))
            workflow = self.catalog["companies"]["sol"]["workflows"][0]
            saved = store.capture("sol", workflow, "Teste")
            restored = store.load("sol", "cadastro_produtos", saved["id"])
            self.assertEqual("Cadastro de Produtos", restored["name"])
            version_path = next((Path(temporary) / "workflow-versions").rglob("*.json"))
            version_path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "inválida|adulterada"):
                store.load("sol", "cadastro_produtos", saved["id"])

    def test_persistent_queue_pauses_resumes_cancels_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            queue = PersistentExecutionQueue(Path(temporary))
            jobs = queue.enqueue(
                "sol",
                ["cadastro_produtos", "transfer_ncias", "estoque_disponivel"],
                "all",
            )
            queue.pause()
            self.assertIsNone(queue.claim())
            queue.resume()
            claimed = queue.claim()
            self.assertEqual(jobs[0]["id"], claimed["id"])
            self.assertEqual("running", queue.snapshot()["jobs"][0]["status"])
            recovered = PersistentExecutionQueue(Path(temporary))
            self.assertEqual("queued", recovered.snapshot()["jobs"][0]["status"])
            claimed = recovered.claim()
            recovered.cancel(claimed["id"])
            self.assertTrue(recovered.cancellation_requested(claimed["id"]))
            finished = recovered.finish(claimed["id"], {"ok": False})
            self.assertEqual("cancelled", finished["status"])
            cancelled = recovered.cancel(jobs[1]["id"])
            self.assertEqual("cancelled", cancelled["status"])
            removed_cancelled = recovered.remove(jobs[1]["id"])
            self.assertEqual("cancelled", removed_cancelled["status"])
            failed_job = recovered.claim()
            with self.assertRaisesRegex(ValueError, "finalização"):
                recovered.remove(failed_job["id"])
            recovered.finish(failed_job["id"], {"ok": False, "error": "Teste"})
            removed_failed = recovered.remove(failed_job["id"])
            self.assertEqual("failed", removed_failed["status"])
            remaining_ids = [item["id"] for item in recovered.snapshot()["jobs"]]
            self.assertNotIn(jobs[1]["id"], remaining_ids)
            self.assertNotIn(failed_job["id"], remaining_ids)

    def test_persistent_queue_quarantines_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = PersistentExecutionQueue(root)
            queue.enqueue("sol", ["cadastro_produtos"], "all")
            path = root / "execution-queue.json"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "cadastro_produtos", "unknown_workflow"
                ),
                encoding="utf-8",
            )
            recovered = PersistentExecutionQueue(root)
            self.assertEqual([], recovered.snapshot()["jobs"])
            self.assertEqual(1, len(list(root.glob("execution-queue-tampered-*.json"))))

    def test_dashboard_exposes_v2_platform_and_migrates_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / "seed.json"
            source = (
                Path(__file__).resolve().parents[1]
                / "src"
                / "santri_automation"
                / "resources"
                / "config"
                / "export_catalog.json"
            )
            catalog = json.loads(source.read_text(encoding="utf-8"))
            catalog["version"] = 1
            seed.write_text(json.dumps(catalog), encoding="utf-8")
            store = ExportCatalog(seed, root / "catalog.json")
            api = DashboardApi(catalog=store)
            state = api.get_state()
            self.assertEqual(2, state["version"])
            self.assertEqual(2, state["application"]["platform"]["catalog_version"])
            self.assertEqual(
                "production", state["companies"]["sol"]["workflows"][0]["lifecycle"]
            )
            result = api.simulate_workflow("sol", "cadastro_produtos")
            self.assertTrue(result["ready"])
            api.execution_queue = PersistentExecutionQueue(root)
            queued = api.execution_queue.enqueue("sol", ["cadastro_produtos"], "all")[0]
            claimed = api.execution_queue.claim()
            self.assertEqual(queued["id"], claimed["id"])
            api.execution_queue.finish(claimed["id"], {"ok": False, "error": "Teste"})
            removed = api.remove_queue_item(claimed["id"])
            self.assertTrue(removed["ok"])
            self.assertEqual([], removed["queue"]["jobs"])


if __name__ == "__main__":
    unittest.main()
