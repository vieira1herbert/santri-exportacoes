from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import build_app
from santri_automation import __version__
from santri_automation.catalog import ExportCatalog
from santri_automation.reliability import ReliabilityCenter
from santri_automation.resource_paths import resource_path
from santri_automation.security import (
    FileIntegrityService,
    SecurityViolation,
    UpdateScriptPolicy,
    WindowsSecurityService,
)
from santri_automation.windows_driver import WindowsSantriDriver


class SecurityV14Test(unittest.TestCase):
    def test_integrity_detects_file_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "catalog.json"
            path.write_text('{"safe": true}', encoding="utf-8")
            service = FileIntegrityService(root)
            service.seal_file(path)
            self.assertTrue(service.verify_file(path))
            path.write_text('{"safe": false}', encoding="utf-8")
            self.assertFalse(service.verify_file(path))
            with self.assertRaises(SecurityViolation):
                service.require_file(path)

    def test_catalog_is_quarantined_after_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = ExportCatalog(
                resource_path("config", "export_catalog.json"),
                root / "export_catalog.json",
            )
            catalog.save(catalog.load())
            catalog.user_path.write_text("{}", encoding="utf-8")
            with self.assertRaises(SecurityViolation):
                catalog.load()
            evidence = list(
                (root / "quarantine").glob("export_catalog-tampered-*.json")
            )
            self.assertEqual(len(evidence), 1)

    def test_history_chain_detects_changed_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = ExportCatalog(
                resource_path("config", "export_catalog.json"),
                root / "export_catalog.json",
            )
            catalog.save(catalog.load())
            catalog.append_history({"message": "Evento legítimo"})
            data = catalog.load()
            self.assertTrue(catalog.verify_history_chain(data))
            data["history"][0]["message"] = "Evento alterado"
            self.assertFalse(catalog.verify_history_chain(data))

    def test_catalog_recovers_latest_verified_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = ExportCatalog(
                resource_path("config", "export_catalog.json"),
                root / "export_catalog.json",
            )
            data = catalog.load()
            catalog.save(data)
            catalog.create_manual_backup()
            catalog.user_path.write_text("{}", encoding="utf-8")
            recovered = catalog.load()
            self.assertEqual(set(recovered["companies"]), {"sol", "horus"})
            self.assertTrue(catalog.integrity.verify_file(catalog.user_path))

    def test_update_policy_accepts_only_authorized_regular_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / "ShellEstoqueDisp.ps1"
            valid.write_text("Write-Output OK", encoding="utf-8")
            self.assertEqual(UpdateScriptPolicy.authorize(valid, root), valid.resolve())
            invalid = root / "executar.ps1"
            invalid.write_text("Write-Output OK", encoding="utf-8")
            with self.assertRaises(SecurityViolation):
                UpdateScriptPolicy.authorize(invalid, root)

    def test_powershell_command_has_no_policy_bypass(self) -> None:
        command = WindowsSantriDriver._powershell_file_command(Path("authorized.ps1"))
        self.assertNotIn("Bypass", command)
        self.assertNotIn("-ExecutionPolicy", command)
        self.assertTrue(Path(command[0]).is_absolute())
        self.assertEqual(command[-2], "-File")

    def test_support_package_redacts_log_and_is_sealed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "app-errors.log"
            log.write_text("senha=segredo", encoding="utf-8")
            center = ReliabilityCenter(root)
            package = center.create_support_package({}, {}, log)
            self.assertTrue(center.integrity.verify_file(package))
            with zipfile.ZipFile(package) as archive:
                content = archive.read("app-errors.log").decode("utf-8")
            self.assertNotIn("segredo", content)
            self.assertIn("[PROTEGIDO]", content)

    def test_release_manifest_contains_hashes_and_signature_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "app.exe"
            sbom = root / "sbom.json"
            executable.write_bytes(b"application")
            sbom.write_text("{}", encoding="utf-8")
            original = build_app.OUTPUT_ROOT
            build_app.OUTPUT_ROOT = root
            try:
                manifest = build_app.generate_release_manifest(
                    executable,
                    sbom,
                    {"signed": False, "status": "not_configured"},
                )
            finally:
                build_app.OUTPUT_ROOT = original
            value = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(value["version"], __version__)
            self.assertEqual(
                value["executable"]["sha256"], build_app.sha256(executable)
            )
            self.assertFalse(value["authenticode"]["signed"])

    def test_unsigned_verified_release_remains_operational(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog.json"
            catalog.write_text("{}", encoding="utf-8")
            integrity = FileIntegrityService(root)
            integrity.seal_file(catalog)
            service = WindowsSecurityService(root, integrity)
            service.release_status = lambda: {
                "mode": "packaged",
                "verified": True,
                "signed": False,
                "signature_status": "not_configured",
            }
            status = service.status(catalog, True)
            self.assertTrue(status["ready"])
            self.assertFalse(status["release"]["signed"])


if __name__ == "__main__":
    unittest.main()
