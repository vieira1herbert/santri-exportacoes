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

    def test_schedule_priority_options_have_descriptive_labels(self) -> None:
        dashboard = (UI_ROOT / "dashboard.html").read_text(encoding="utf-8")
        for label in (
            "1 · Baixa",
            "2 · Moderada",
            "3 · Normal",
            "4 · Alta",
            "5 · Crítica",
        ):
            self.assertIn(label, dashboard)

    def test_schedule_exceptions_use_a_brazilian_visual_date_editor(self) -> None:
        dashboard = (UI_ROOT / "dashboard.html").read_text(encoding="utf-8")
        entrypoint = (UI_ROOT / "scripts" / "app.js").read_text(encoding="utf-8")
        editor = (
            UI_ROOT / "scripts" / "features" / "scheduling" / "exception-date-editor.js"
        ).read_text(encoding="utf-8")
        self.assertIn('id="schedule-exception-date"', dashboard)
        self.assertIn(
            'id="schedule-exception-date" class="form-control exception-date-trigger" type="button"',
            dashboard,
        )
        self.assertIn('id="schedule-exception-calendar"', dashboard)
        self.assertIn('id="schedule-exception-grid"', dashboard)
        self.assertIn('aria-haspopup="dialog"', dashboard)
        self.assertIn("DD/MM/AAAA", dashboard)
        self.assertNotIn('id="schedule-exceptions"', dashboard)
        self.assertIn("new ExceptionDateEditor", entrypoint)
        self.assertIn("renderCalendar()", editor)
        self.assertIn("`${day}/${month}/${year}`", editor)

    def test_top_navigation_uses_home_instead_of_redundant_back_buttons(self) -> None:
        dashboard = (UI_ROOT / "dashboard.html").read_text(encoding="utf-8")
        scripts = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (UI_ROOT / "scripts").rglob("*.js")
        )
        self.assertIn('id="home-button"', dashboard)
        self.assertIn("session.activePage === 'dashboard'", scripts)
        self.assertNotIn("Voltar às exportações", scripts)

    def test_all_selects_use_the_shared_thematic_component(self) -> None:
        entrypoint = (UI_ROOT / "scripts" / "app.js").read_text(encoding="utf-8")
        styles = (UI_ROOT / "styles" / "app.css").read_text(encoding="utf-8")
        service = (
            UI_ROOT / "scripts" / "shared" / "custom-select-service.js"
        ).read_text(encoding="utf-8")
        self.assertIn("new CustomSelectService(document)", entrypoint)
        self.assertIn("customSelects.start()", entrypoint)
        self.assertIn('@import url("./select.css")', styles)
        self.assertIn("select.form-select:not([data-custom-select])", service)
        self.assertIn("aria-selected", service)

    def test_platform_allows_audited_removal_of_terminal_queue_items(self) -> None:
        facade = (SOURCE_ROOT / "desktop_app.py").read_text(encoding="utf-8")
        entrypoint = (UI_ROOT / "scripts" / "app.js").read_text(encoding="utf-8")
        queue = (SOURCE_ROOT / "services" / "execution_queue.py").read_text(
            encoding="utf-8"
        )
        presenter = (
            UI_ROOT / "scripts" / "features" / "platform" / "platform-presenter.js"
        ).read_text(encoding="utf-8")
        self.assertIn("def remove_queue_item", facade)
        self.assertIn("api.remove_queue_item", facade)
        self.assertIn("def remove(self, job_id", queue)
        self.assertIn("platform-remove", presenter)
        self.assertIn("const jobId = event.currentTarget.dataset.job", entrypoint)
        self.assertIn("api().remove_queue_item(jobId)", entrypoint)

    def test_release_header_and_primary_palette_are_current(self) -> None:
        presenter = (
            UI_ROOT / "scripts" / "features" / "releases" / "release-presenter.js"
        ).read_text(encoding="utf-8")
        core = (UI_ROOT / "styles" / "core.css").read_text(encoding="utf-8")
        self.assertNotIn("DISTRIBUIÇÃO CONTROLADA · V1.7", presenter)
        self.assertIn("--primary: #2f719e", core)
        self.assertNotIn("#339cff", core)

    def test_dashboard_has_no_duplicate_ids_or_unlabeled_numeric_options(self) -> None:
        dashboard = (UI_ROOT / "dashboard.html").read_text(encoding="utf-8")
        element_ids = re.findall(r'\bid="([^"]+)"', dashboard)
        self.assertEqual(len(element_ids), len(set(element_ids)))
        option_labels = re.findall(r"<option[^>]*>(.*?)</option>", dashboard)
        self.assertTrue(option_labels)
        for label in option_labels:
            normalized = re.sub(r"<[^>]+>", "", label).strip()
            self.assertTrue(normalized)
            self.assertFalse(normalized.isdigit(), normalized)


if __name__ == "__main__":
    unittest.main()
