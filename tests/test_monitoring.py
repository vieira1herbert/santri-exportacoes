from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))


from santri_automation.reliability import ReliabilityCenter
from santri_automation.services.operational_monitoring import OperationalMonitoring
from santri_automation.services.system_diagnostics import SystemDiagnostics


class OperationalMonitoringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.current = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
        self.monitoring = OperationalMonitoring(now=lambda: self.current)
        self.state = {
            "companies": {
                "sol": {
                    "workflows": [
                        {
                            "id": "cadastro_produtos",
                            "name": "Cadastro de Produtos",
                            "implemented": True,
                            "enabled": True,
                            "schedule": {"enabled": False, "entries": []},
                        }
                    ]
                },
                "horus": {"workflows": []},
            },
            "history": [],
        }
        self.health = {
            "ready": True,
            "companies": {"sol": {"ready": True}, "horus": {"ready": True}},
            "runtime": {
                "session_unlocked": True,
                "santri_open": {"sol": True, "horus": False},
            },
        }
        self.security = {"ready": True}

    def test_snapshot_calculates_real_success_and_duration(self) -> None:
        reports = [
            self.report("success", 120, 1),
            self.report("failed", 60, 2),
        ]
        result = self.monitoring.snapshot(
            self.state,
            reports,
            self.health,
            self.security,
        )
        self.assertEqual(2, result["overview"]["executions_30d"])
        self.assertEqual(50, result["overview"]["success_rate_30d"])
        self.assertEqual(90, result["overview"]["average_duration_seconds"])
        self.assertEqual("healthy", result["status"])
        workflow = result["companies"]["sol"]["workflows"][0]
        self.assertEqual(50, workflow["success_rate_30d"])

    def test_missed_schedule_becomes_operational_alert(self) -> None:
        self.state["companies"]["sol"]["workflows"][0]["schedule"] = {
            "enabled": True,
            "entries": [{"weekday": self.current.weekday(), "time": "10:00"}],
        }
        result = self.monitoring.snapshot(
            self.state,
            [],
            self.health,
            self.security,
        )
        self.assertEqual("attention", result["status"])
        self.assertEqual("Agendamento não executado", result["alerts"][0]["title"])

    def test_recorded_schedule_does_not_raise_false_alert(self) -> None:
        workflow = self.state["companies"]["sol"]["workflows"][0]
        workflow["schedule"] = {
            "enabled": True,
            "entries": [{"weekday": self.current.weekday(), "time": "10:00"}],
        }
        workflow["last_scheduled_slot"] = "2026-08-13T10:00"
        result = self.monitoring.snapshot(
            self.state,
            [],
            self.health,
            self.security,
        )
        self.assertEqual([], result["alerts"])

    def test_summary_contains_support_information(self) -> None:
        result = self.monitoring.snapshot(
            self.state,
            [self.report("success", 75, 1)],
            self.health,
            self.security,
        )
        summary = self.monitoring.technical_summary(
            result,
            self.health,
            self.security,
        )
        self.assertIn("RESUMO OPERACIONAL", summary)
        self.assertIn("Taxa de sucesso em 30 dias: 100%", summary)
        self.assertIn("Nenhum alerta operacional ativo", summary)
        self.assertIn("Nenhuma falha recorrente", summary)

    def test_observability_aggregates_steps_failures_and_artifacts(self) -> None:
        report = self.report("failed", 90, 1)
        started = self.current - timedelta(days=1, seconds=90)
        finished = self.current - timedelta(days=1)
        report["timeline"] = [
            {
                "timestamp": started.isoformat(),
                "step": "Exportar Cadastro",
                "status": "running",
                "message": "Tentativa 1",
            },
            {
                "timestamp": (started + timedelta(seconds=30)).isoformat(),
                "step": "Exportar Cadastro",
                "status": "retry",
                "message": "Timeout após 30 segundos",
            },
            {
                "timestamp": finished.isoformat(),
                "step": "Exportar Cadastro",
                "status": "error",
                "message": "Timeout após 60 segundos",
            },
        ]
        report["artifacts"] = [r"S:\SOL\cadastro.ods"]
        report["artifact_manifest"] = [
            {
                "name": "cadastro.ods",
                "path": r"S:\SOL\cadastro.ods",
                "size": 2048,
                "sha256": "abc123",
            }
        ]
        result = self.monitoring.snapshot(
            self.state,
            [report],
            self.health,
            self.security,
        )["observability"]
        step = result["step_performance"][0]
        self.assertEqual("Exportar Cadastro", step["step"])
        self.assertEqual(1, step["failures"])
        self.assertEqual(1, step["retries"])
        self.assertEqual(90, step["average_duration_seconds"])
        self.assertEqual(1, result["recurring_failures"][0]["count"])
        self.assertEqual("cadastro.ods", result["recent_artifacts"][0]["name"])
        self.assertEqual("abc123", result["recent_artifacts"][0]["sha256"])

    def report(self, status: str, duration: int, days_ago: int) -> dict:
        finished = self.current - timedelta(days=days_ago)
        return {
            "status": status,
            "company": "sol",
            "workflow_ids": ["cadastro_produtos"],
            "action": "all",
            "started_at": (finished - timedelta(seconds=duration)).isoformat(),
            "finished_at": finished.isoformat(),
        }


class OperationalPreflightTest(unittest.TestCase):
    def test_preflight_reports_runtime_and_required_paths(self) -> None:
        company = SimpleNamespace(shortcut=Path("Santri.lnk"))
        config = SimpleNamespace(companies={"sol": company})
        diagnostics = SystemDiagnostics(
            SimpleNamespace(user_path=Path("catalog.json")),
            Path("config.json"),
            config_loader=lambda _path: config,
        )
        state = {
            "settings": {"downloads_folder": "Downloads"},
            "companies": {
                "sol": {
                    "workflows": [
                        {
                            "id": "cadastro_produtos",
                            "name": "Cadastro de Produtos",
                            "destination": "Destino",
                        }
                    ]
                }
            },
        }
        with (
            patch.object(
                SystemDiagnostics,
                "runtime_status",
                return_value={
                    "session_unlocked": True,
                    "santri_open": {"sol": False},
                },
            ),
            patch.object(SystemDiagnostics, "path_status", return_value=True),
        ):
            result = diagnostics.execution_preflight(
                state,
                "sol",
                ["cadastro_produtos"],
                "export",
            )
        self.assertTrue(result["ready"])
        self.assertIn("Sessão Windows", [item["name"] for item in result["checks"]])
        self.assertIn(
            "Pasta local de exportação", [item["name"] for item in result["checks"]]
        )

    def test_artifact_retention_removes_only_expired_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            center = ReliabilityCenter(Path(temporary))
            reports = center.root / "reports"
            reports.mkdir(parents=True)
            old = reports / "old.json"
            recent = reports / "recent.json"
            old.write_text("{}", encoding="utf-8")
            recent.write_text("{}", encoding="utf-8")
            expired = datetime.now().timestamp() - 100 * 86400
            os.utime(old, (expired, expired))
            removed = center.apply_retention(90)
            self.assertFalse(old.exists())
            self.assertTrue(recent.exists())
            self.assertEqual(1, removed["reports"])


if __name__ == "__main__":
    unittest.main()
