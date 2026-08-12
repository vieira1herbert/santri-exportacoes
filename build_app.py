from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = PROJECT_ROOT / "dist"
WORK_ROOT = PROJECT_ROOT / ".build" / "pyinstaller"
APP_NAME = "Santri Exportações"
ICON_PATH = PROJECT_ROOT / "src" / "santri_automation" / "resources" / "ui" / "assets" / "sh-app-icon.ico"
RESOURCES_PATH = PROJECT_ROOT / "src" / "santri_automation" / "resources"


def pyinstaller_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(ICON_PATH),
        "--paths",
        str(PROJECT_ROOT / "src"),
        "--add-data",
        f"{RESOURCES_PATH}{os.pathsep}santri_automation/resources",
        "--collect-all",
        "webview",
        "--hidden-import",
        "webview.platforms.edgechromium",
        "--distpath",
        str(OUTPUT_ROOT),
        "--workpath",
        str(WORK_ROOT),
        "--specpath",
        str(WORK_ROOT),
        str(PROJECT_ROOT / "run_local_app.py"),
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_version() -> str:
    content = (PROJECT_ROOT / "src" / "santri_automation" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if not match:
        raise ValueError("Versão do aplicativo não encontrada.")
    return match.group(1)


def git_commit() -> str:
    candidates = [
        Path(value)
        for value in (
            os.environ.get("SANTRI_GIT", ""),
            shutil.which("git") or "",
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "cmd" / "git.exe"),
            str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "cmd" / "git.exe"),
        )
        if value
    ]
    git = next((path for path in candidates if path.is_file()), None)
    if git is None:
        return "unavailable"
    result = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def generate_sbom() -> Path:
    components = []
    distributions = sorted(
        importlib.metadata.distributions(),
        key=lambda item: str(item.metadata.get("Name") or "").casefold(),
    )
    for distribution in distributions:
        name = distribution.metadata["Name"]
        if name:
            components.append(
                {
                    "type": "library",
                    "name": name,
                    "version": distribution.version,
                    "purl": f"pkg:pypi/{name.casefold().replace('_', '-')}@{distribution.version}",
                }
            )
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid5(NAMESPACE_URL, git_commit())}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "component": {
                "type": "application",
                "name": "santri-exportacoes",
                "version": project_version(),
                "authors": [{"name": "Herbert Vieira"}],
            },
        },
        "components": components,
    }
    path = OUTPUT_ROOT / "santri-exportacoes-sbom.cdx.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def sign_executable(executable: Path) -> dict[str, str | bool]:
    signtool = os.environ.get("SANTRI_SIGNTOOL", "").strip()
    thumbprint = os.environ.get("SANTRI_CERT_THUMBPRINT", "").strip()
    if not signtool or not thumbprint:
        return {"signed": False, "status": "not_configured"}
    timestamp_url = os.environ.get("SANTRI_TIMESTAMP_URL", "http://timestamp.digicert.com").strip()
    subprocess.run(
        [signtool, "sign", "/sha1", thumbprint, "/fd", "SHA256", "/tr", timestamp_url, "/td", "SHA256", str(executable)],
        check=True,
    )
    subprocess.run([signtool, "verify", "/pa", "/v", str(executable)], check=True)
    return {"signed": True, "status": "verified", "certificate_thumbprint": thumbprint}


def generate_release_manifest(executable: Path, sbom: Path, signature: dict[str, str | bool]) -> Path:
    document = {
        "application": "Santri Exportações",
        "version": project_version(),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "executable": {
            "name": executable.name,
            "size": executable.stat().st_size,
            "sha256": sha256(executable),
        },
        "sbom": {"name": sbom.name, "sha256": sha256(sbom)},
        "authenticode": signature,
    }
    path = OUTPUT_ROOT / "santri-exportacoes-release.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def create_desktop_shortcut(executable: Path) -> Path:
    from win32com.client import Dispatch

    shortcut_path = Path.home() / "Desktop" / f"{APP_NAME}.lnk"
    shortcut = Dispatch("WScript.Shell").CreateShortcut(str(shortcut_path))
    shortcut.TargetPath = str(executable)
    shortcut.WorkingDirectory = str(PROJECT_ROOT)
    shortcut.IconLocation = f"{executable},0"
    shortcut.Description = "Automação local de exportações do Santri"
    shortcut.Save()
    return shortcut_path


def remove_legacy_artifacts() -> None:
    desktop = Path.home() / "Desktop"
    for legacy_name in ("Santri Export", "Santri ExportaÃ§Ãµes"):
        for path in (desktop / f"{legacy_name}.lnk", OUTPUT_ROOT / f"{legacy_name}.exe"):
            if path.is_file():
                path.unlink()


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if WORK_ROOT.exists():
        shutil.rmtree(WORK_ROOT)
    subprocess.run(pyinstaller_command(), cwd=PROJECT_ROOT, check=True)
    executable = OUTPUT_ROOT / f"{APP_NAME}.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"O executável não foi gerado: {executable}")
    signature = sign_executable(executable)
    sbom = generate_sbom()
    manifest = generate_release_manifest(executable, sbom, signature)
    shortcut = create_desktop_shortcut(executable)
    remove_legacy_artifacts()
    print(f"Executável: {executable}")
    print(f"Atalho: {shortcut}")
    print(f"SBOM: {sbom}")
    print(f"Manifesto: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
