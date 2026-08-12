from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = PROJECT_ROOT / "dist"
WORK_ROOT = PROJECT_ROOT / ".build" / "pyinstaller"
APP_NAME = "Santri Exportações"
ICON_PATH = (
    PROJECT_ROOT
    / "src"
    / "santri_automation"
    / "resources"
    / "ui"
    / "assets"
    / "sh-app-icon.ico"
)
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


def create_desktop_shortcut(executable: Path) -> Path:
    from win32com.client import Dispatch

    desktop = Path.home() / "Desktop"
    shortcut_path = desktop / f"{APP_NAME}.lnk"
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
        for path in (
            desktop / f"{legacy_name}.lnk",
            OUTPUT_ROOT / f"{legacy_name}.exe",
        ):
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
    shortcut = create_desktop_shortcut(executable)
    remove_legacy_artifacts()
    print(f"Executável: {executable}")
    print(f"Atalho: {shortcut}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
