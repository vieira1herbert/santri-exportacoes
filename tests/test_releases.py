from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

from santri_automation.services.release_manager import ReleaseManager


class TestableReleaseManager(ReleaseManager):
    def __init__(self, *args, downloads: dict[str, bytes], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.downloads = downloads

    def _download(self, url: str, destination: Path, maximum: int) -> None:
        value = self.downloads[url]
        if len(value) > maximum:
            raise ValueError("Pacote excedeu o limite.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(value)


class ReleaseManagementTest(unittest.TestCase):
    def test_check_uses_selected_channel_and_reports_no_published_release(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def read(self, _maximum: int) -> bytes:
                return b"[]"

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = ReleaseManager(root, "1.7.0", root / "CHANGELOG.md")
            manager.save_preferences({"channel": "test"})
            with patch("santri_automation.services.release_manager.urllib.request.urlopen", return_value=Response()):
                result = manager.check("stable")
            self.assertTrue(result["ok"])
            self.assertFalse(result["published"])
            self.assertEqual("stable", result["channel"])

    def test_preferences_isolate_environment_and_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notes = root / "CHANGELOG.md"
            notes.write_text("## 1.7.0\n- Atualização segura\n", encoding="utf-8")
            manager = ReleaseManager(root, "1.7.0", notes)
            saved = manager.save_preferences({"environment": "homologation", "channel": "test", "automatic_check": True})
            self.assertEqual("homologation", saved["environment"])
            self.assertEqual("test", manager.status()["channel"])

    def test_prepare_update_backs_up_and_verifies_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = b"verified executable"
            digest = hashlib.sha256(executable).hexdigest()
            manifest = json.dumps({"version": "1.8.0", "executable": {"sha256": digest}}).encode()
            manager = TestableReleaseManager(root, "1.7.0", root / "notes.md", downloads={"manifest": manifest, "executable": executable})
            catalog = root / "catalog.json"
            catalog.write_text('{"companies":{}}', encoding="utf-8")
            release = {"latest_version": "1.8.0", "assets": [{"name": "santri-exportacoes-release.json", "url": "manifest"}, {"name": "Santri Exportações.exe", "url": "executable"}]}
            result = manager.prepare_update(release, catalog)
            self.assertTrue(result["ok"])
            self.assertTrue(Path(result["catalog_backup"]).is_file())
            self.assertEqual(executable, Path(result["path"]).read_bytes())

    def test_prepared_upgrade_is_not_a_rollback_and_current_release_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current_executable = root / "current.exe"
            current_executable.write_bytes(b"current release")
            next_executable = b"next release"
            digest = hashlib.sha256(next_executable).hexdigest()
            manifest = json.dumps({"version": "1.8.0", "executable": {"sha256": digest}}).encode()
            manager = TestableReleaseManager(root, "1.7.0", root / "notes.md", downloads={"manifest": manifest, "executable": next_executable})
            release = {"latest_version": "1.8.0", "assets": [{"name": "santri-exportacoes-release.json", "url": "manifest"}, {"name": "Santri Exportações.exe", "url": "executable"}]}
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(current_executable)):
                manager.prepare_update(release, root / "catalog.json")
            self.assertFalse(manager.status()["rollback_available"])
            previous = ReleaseManager(root, "1.8.0", root / "notes.md").rollback_plan()
            self.assertTrue(previous["ok"])
            self.assertEqual("1.7.0", previous["version"])

    def test_prepare_update_rejects_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = json.dumps({"version": "1.8.0", "executable": {"sha256": "0" * 64}}).encode()
            manager = TestableReleaseManager(root, "1.7.0", root / "notes.md", downloads={"manifest": manifest, "executable": b"changed"})
            release = {"latest_version": "1.8.0", "assets": [{"name": "santri-exportacoes-release.json", "url": "manifest"}, {"name": "Santri Exportações.exe", "url": "executable"}]}
            with self.assertRaisesRegex(ValueError, "não corresponde"):
                manager.prepare_update(release, root / "missing.json")

    def test_release_notes_are_loaded_for_the_application(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notes = root / "CHANGELOG.md"
            notes.write_text("## 1.7.0 — Atualização\n- Ambiente isolado\n- Reversão\n", encoding="utf-8")
            result = ReleaseManager(root, "1.7.0", notes).release_notes()
            self.assertEqual("1.7.0 — Atualização", result[0]["title"])
            self.assertIn("Reversão", result[0]["body"])


if __name__ == "__main__":
    unittest.main()
