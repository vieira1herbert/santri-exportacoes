from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src" / "santri_automation"
UI_ROOT = SOURCE_ROOT / "resources" / "ui"


class ArchitectureTest(unittest.TestCase):
    def test_dashboard_is_only_the_document_shell(self) -> None:
        dashboard = (UI_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertNotIn("<style>", dashboard)
        self.assertNotRegex(dashboard, r"<script>(?:.|\n)*?</script>")
        self.assertIn("./styles/app.css", dashboard)
        self.assertIn("./scripts/app.js", dashboard)

    def test_styles_are_partitioned_by_responsibility(self) -> None:
        entrypoint = (UI_ROOT / "styles" / "app.css").read_text(encoding="utf-8")
        imports = re.findall(r'@import url\("\./([^"]+)"\)', entrypoint)
        self.assertGreaterEqual(len(imports), 8)
        for relative_path in imports:
            self.assertTrue((UI_ROOT / "styles" / relative_path).is_file())

    def test_javascript_entrypoint_uses_explicit_modules(self) -> None:
        entrypoint = (UI_ROOT / "scripts" / "app.js").read_text(encoding="utf-8")
        imports = re.findall(r"from '([^']+)'", entrypoint)
        self.assertGreaterEqual(len(imports), 8)
        for relative_path in imports:
            self.assertTrue((UI_ROOT / "scripts" / relative_path).resolve().is_file())
        self.assertIn("new DashboardSession", entrypoint)
        self.assertIn("new PageRouter", entrypoint)
        self.assertIn("new BridgeClient", entrypoint)

    def test_python_api_delegates_diagnostics_to_a_service(self) -> None:
        facade = (SOURCE_ROOT / "desktop_app.py").read_text(encoding="utf-8")
        service = (SOURCE_ROOT / "services" / "system_diagnostics.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("class SystemDiagnostics", service)
        self.assertIn("self.diagnostics.detailed_health", facade)
        self.assertIn("self.diagnostics.system_health", facade)

    def test_v15_monitoring_is_separated_from_the_desktop_facade(self) -> None:
        facade = (SOURCE_ROOT / "desktop_app.py").read_text(encoding="utf-8")
        service = (SOURCE_ROOT / "services" / "operational_monitoring.py").read_text(
            encoding="utf-8"
        )
        presenter = (
            UI_ROOT / "scripts" / "features" / "monitoring" / "monitoring-presenter.js"
        ).read_text(encoding="utf-8")
        self.assertIn("OperationalMonitoring", facade)
        self.assertIn("class OperationalMonitoring", service)
        self.assertIn("class MonitoringPresenter", presenter)

    def test_v16_scheduling_is_separated_from_the_desktop_facade(self) -> None:
        facade = (SOURCE_ROOT / "desktop_app.py").read_text(encoding="utf-8")
        service = (SOURCE_ROOT / "services" / "schedule_center.py").read_text(
            encoding="utf-8"
        )
        presenter = (
            UI_ROOT / "scripts" / "features" / "scheduling" / "schedule-presenter.js"
        ).read_text(encoding="utf-8")
        self.assertIn("ScheduleCenter", facade)
        self.assertIn("class ScheduleCenter", service)
        self.assertIn("class SchedulePresenter", presenter)

    def test_v17_release_management_is_separated_from_the_desktop_facade(self) -> None:
        facade = (SOURCE_ROOT / "desktop_app.py").read_text(encoding="utf-8")
        service = (SOURCE_ROOT / "services" / "release_manager.py").read_text(
            encoding="utf-8"
        )
        presenter = (
            UI_ROOT / "scripts" / "features" / "releases" / "release-presenter.js"
        ).read_text(encoding="utf-8")
        self.assertIn("ReleaseManager", facade)
        self.assertIn("class ReleaseManager", service)
        self.assertIn("class ReleasePresenter", presenter)

    def test_v20_platform_separates_domain_and_services(self) -> None:
        facade = (SOURCE_ROOT / "platform.py").read_text(encoding="utf-8")
        desktop = (SOURCE_ROOT / "desktop_app.py").read_text(encoding="utf-8")
        blueprints = (SOURCE_ROOT / "domain" / "workflow_blueprints.py").read_text(
            encoding="utf-8"
        )
        simulator = (SOURCE_ROOT / "services" / "workflow_simulator.py").read_text(
            encoding="utf-8"
        )
        versions = (SOURCE_ROOT / "services" / "workflow_versions.py").read_text(
            encoding="utf-8"
        )
        queue = (SOURCE_ROOT / "services" / "execution_queue.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("class WorkflowBlueprintRegistry", blueprints)
        self.assertIn("class WorkflowSimulator", simulator)
        self.assertIn("class WorkflowVersionStore", versions)
        self.assertIn("class PersistentExecutionQueue", queue)
        self.assertNotIn("class PersistentExecutionQueue", facade)
        self.assertIn("self.execution_queue", desktop)

    def test_corporate_installer_definition_exists(self) -> None:
        definition = (PROJECT_ROOT / "installer" / "SantriExportacoes.iss").read_text(
            encoding="utf-8"
        )
        self.assertIn("PrivilegesRequired=lowest", definition)
        self.assertIn("UninstallDisplayIcon", definition)

    def test_ui_resources_are_valid_utf8_without_mojibake(self) -> None:
        forbidden = ("\u00c3\u0192", "\u00c3\u201a", "\ufffd")
        paths = [UI_ROOT / "dashboard.html"]
        paths.extend((UI_ROOT / "styles").glob("*.css"))
        paths.extend((UI_ROOT / "scripts").rglob("*.js"))
        for path in paths:
            content = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, content, str(path))

    def test_build_pipeline_has_no_versioned_powershell(self) -> None:
        self.assertEqual([], list(PROJECT_ROOT.rglob("*.ps1")))
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("powershell", workflow.casefold())
        self.assertIn("python build_app.py", workflow)


if __name__ == "__main__":
    unittest.main()
