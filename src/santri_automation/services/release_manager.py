from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse


class ReleaseManager:
    API_URL = "https://api.github.com/repos/vieira1herbert/santri-exportacoes/releases"
    ALLOWED_HOSTS: ClassVar = {
        "api.github.com",
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }

    def __init__(self, root: Path, current_version: str, changelog_path: Path) -> None:
        self.root = root / "release-management"
        self.current_version = current_version
        self.changelog_path = changelog_path
        self.preferences_path = self.root / "preferences.json"
        self.installed_path = self.root / "installed.json"

    def status(self) -> dict[str, Any]:
        preferences = self.preferences()
        installed = self._read_json(self.installed_path, [])
        current = self._version_tuple(self.current_version)
        return {
            "current_version": self.current_version,
            "environment": preferences["environment"],
            "channel": preferences["channel"],
            "automatic_check": preferences["automatic_check"],
            "installed": installed if isinstance(installed, list) else [],
            "rollback_available": any(
                self._version_tuple(str(item.get("version") or "")) < current
                for item in installed
                if isinstance(item, dict)
            ),
            "release_notes": self.release_notes(),
            "signature_ready": False,
            "signature_status": "Certificado corporativo ainda não configurado",
        }

    def preferences(self) -> dict[str, Any]:
        value = self._read_json(self.preferences_path, {})
        return {
            "environment": (
                "homologation"
                if value.get("environment") == "homologation"
                else "production"
            ),
            "channel": "test" if value.get("channel") == "test" else "stable",
            "automatic_check": bool(value.get("automatic_check", False)),
        }

    def save_preferences(self, payload: dict[str, Any]) -> dict[str, Any]:
        value = {
            "environment": (
                "homologation"
                if payload.get("environment") == "homologation"
                else "production"
            ),
            "channel": "test" if payload.get("channel") == "test" else "stable",
            "automatic_check": bool(payload.get("automatic_check", False)),
        }
        self._atomic_json(self.preferences_path, value)
        return value

    def check(self, channel: str | None = None) -> dict[str, Any]:
        selected = (
            channel if channel in {"stable", "test"} else self.preferences()["channel"]
        )
        request = urllib.request.Request(
            self.API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Santri-Exportacoes",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                releases = json.loads(response.read(2_000_000).decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            return {
                "ok": False,
                "error": f"Não foi possível consultar o GitHub: {type(error).__name__}.",
            }
        candidates = [
            item
            for item in releases
            if isinstance(item, dict) and not item.get("draft")
        ]
        if selected == "stable":
            candidates = [item for item in candidates if not item.get("prerelease")]
        if not candidates:
            return {
                "ok": True,
                "available": False,
                "published": False,
                "current_version": self.current_version,
                "channel": selected,
            }
        release = candidates[0]
        version = str(release.get("tag_name") or "").lstrip("v")
        return {
            "ok": True,
            "published": True,
            "available": self._version_tuple(version)
            > self._version_tuple(self.current_version),
            "current_version": self.current_version,
            "latest_version": version,
            "channel": selected,
            "name": str(release.get("name") or release.get("tag_name") or version),
            "notes": str(release.get("body") or "")[:8000],
            "published_at": str(release.get("published_at") or ""),
            "url": str(release.get("html_url") or ""),
            "assets": [
                {
                    "name": str(asset.get("name") or ""),
                    "url": str(asset.get("browser_download_url") or ""),
                    "size": int(asset.get("size") or 0),
                }
                for asset in release.get("assets", [])
                if isinstance(asset, dict)
            ],
        }

    def prepare_update(
        self, release: dict[str, Any], catalog_path: Path
    ) -> dict[str, Any]:
        version = str(release.get("latest_version") or "").strip()
        assets = (
            release.get("assets") if isinstance(release.get("assets"), list) else []
        )
        manifest_asset = next(
            (
                item
                for item in assets
                if item.get("name") == "santri-exportacoes-release.json"
            ),
            None,
        )
        executable_asset = next(
            (
                item
                for item in assets
                if str(item.get("name", "")).casefold() == "santri exportações.exe"
            ),
            None,
        )
        if executable_asset is None:
            executable_asset = next(
                (
                    item
                    for item in assets
                    if str(item.get("name", "")).casefold().endswith(".exe")
                    and "setup" not in str(item.get("name", "")).casefold()
                ),
                None,
            )
        if not version or not manifest_asset or not executable_asset:
            raise ValueError("A release não possui manifesto e executável compatíveis.")
        backup = self._backup_catalog(catalog_path, version)
        destination = self.root / "releases" / version
        manifest_path = destination / "santri-exportacoes-release.json"
        executable_path = destination / Path(executable_asset["name"]).name
        self._download(manifest_asset["url"], manifest_path, 2_000_000)
        manifest = self._read_json(manifest_path, {})
        expected = str(manifest.get("executable", {}).get("sha256") or "")
        if manifest.get("version") != version or len(expected) != 64:
            shutil.rmtree(destination, ignore_errors=True)
            raise ValueError("Manifesto da atualização inválido.")
        self._download(executable_asset["url"], executable_path, 150_000_000)
        calculated = self._sha256(executable_path)
        if calculated.casefold() != expected.casefold():
            shutil.rmtree(destination, ignore_errors=True)
            raise ValueError("O executável baixado não corresponde ao manifesto.")
        installed = self._read_json(self.installed_path, [])
        if not isinstance(installed, list):
            installed = []
        installed = self._preserve_current_release(installed, backup)
        installed = [
            item
            for item in installed
            if isinstance(item, dict) and item.get("version") != version
        ]
        installed.insert(
            0,
            {
                "version": version,
                "path": str(executable_path),
                "sha256": calculated,
                "prepared_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "catalog_backup": str(backup),
            },
        )
        self._atomic_json(self.installed_path, installed[:5])
        return {
            "ok": True,
            "version": version,
            "path": str(executable_path),
            "catalog_backup": str(backup),
            "activation": "A nova release está verificada e pronta para ativação controlada.",
        }

    def rollback_plan(self) -> dict[str, Any]:
        installed = self._read_json(self.installed_path, [])
        current = self._version_tuple(self.current_version)
        candidates = [
            item
            for item in installed
            if isinstance(item, dict)
            and self._version_tuple(str(item.get("version") or "")) < current
            and Path(str(item.get("path") or "")).is_file()
        ]
        candidates.sort(
            key=lambda item: self._version_tuple(str(item.get("version") or "")),
            reverse=True,
        )
        candidate = candidates[0] if candidates else None
        if not candidate:
            return {
                "ok": False,
                "error": "Nenhuma release anterior verificada está disponível.",
            }
        return {
            "ok": True,
            "version": candidate["version"],
            "path": candidate["path"],
            "catalog_backup": candidate.get("catalog_backup", ""),
            "requires_restart": True,
        }

    def activate(self, version: str) -> dict[str, Any]:
        installed = self._read_json(self.installed_path, [])
        candidate = next(
            (
                item
                for item in installed
                if isinstance(item, dict) and str(item.get("version")) == str(version)
            ),
            None,
        )
        if not candidate:
            raise ValueError("Release preparada não encontrada.")
        executable = Path(str(candidate.get("path") or "")).resolve()
        release_root = (self.root / "releases").resolve()
        if release_root not in executable.parents or not executable.is_file():
            raise ValueError("Caminho da release preparada é inválido.")
        if (
            self._sha256(executable).casefold()
            != str(candidate.get("sha256") or "").casefold()
        ):
            raise ValueError("A release preparada perdeu a integridade.")
        from win32com.client import Dispatch

        shortcut_path = Path.home() / "Desktop" / "Santri Exportações.lnk"
        shortcut = Dispatch("WScript.Shell").CreateShortcut(str(shortcut_path))
        shortcut.TargetPath = str(executable)
        shortcut.WorkingDirectory = str(executable.parent)
        shortcut.IconLocation = f"{executable},0"
        shortcut.Description = "Santri Exportações · distribuição controlada"
        shortcut.Save()
        self._atomic_json(
            self.root / "active.json",
            {
                "version": version,
                "path": str(executable),
                "activated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        )
        return {
            "ok": True,
            "version": version,
            "path": str(executable),
            "restart_required": True,
        }

    def release_notes(self) -> list[dict[str, str]]:
        if not self.changelog_path.is_file():
            return []
        sections: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        for line in self.changelog_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if current:
                    sections.append(current)
                current = {"title": line[3:].strip(), "body": ""}
            elif current and line.startswith("- "):
                current["body"] += ("\n" if current["body"] else "") + line[2:].strip()
        if current:
            sections.append(current)
        return sections[:5]

    def _preserve_current_release(
        self, installed: list[dict[str, Any]], catalog_backup: Path
    ) -> list[dict[str, Any]]:
        if any(
            str(item.get("version") or "") == self.current_version for item in installed
        ):
            return installed
        if not getattr(sys, "frozen", False):
            return installed
        source = Path(sys.executable).resolve()
        if not source.is_file():
            return installed
        destination = self.root / "releases" / self.current_version / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return [
            {
                "version": self.current_version,
                "path": str(destination),
                "sha256": self._sha256(destination),
                "prepared_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "catalog_backup": str(catalog_backup),
            },
            *installed,
        ]

    def _backup_catalog(self, path: Path, target_version: str) -> Path:
        destination = (
            self.root
            / "pre-update-backups"
            / f"before-{target_version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            shutil.copy2(path, destination)
        else:
            destination.write_text("{}\n", encoding="utf-8")
        return destination

    def _download(self, url: str, destination: Path, maximum: int) -> None:
        parsed = urlparse(str(url))
        if parsed.scheme != "https" or parsed.hostname not in self.ALLOWED_HOSTS:
            raise ValueError("Origem de atualização não autorizada.")
        request = urllib.request.Request(
            url, headers={"User-Agent": "Santri-Exportacoes"}
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with (
            urllib.request.urlopen(request, timeout=30) as response,
            temporary.open("wb") as stream,
        ):
            final = urlparse(response.geturl())
            if final.scheme != "https" or final.hostname not in self.ALLOWED_HOSTS:
                raise ValueError("Redirecionamento de atualização não autorizado.")
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > maximum:
                    raise ValueError(
                        "Pacote de atualização excedeu o limite permitido."
                    )
                stream.write(chunk)
        temporary.replace(destination)

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        numbers = re.findall(r"\d+", value)
        return tuple(int(part) for part in numbers[:3]) if numbers else (0,)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _read_json(path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
