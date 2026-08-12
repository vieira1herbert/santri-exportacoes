from __future__ import annotations

import subprocess
import sys
import winreg
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Santri Exportacoes"


def configure_startup(enabled: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(
                key,
                VALUE_NAME,
                0,
                winreg.REG_SZ,
                startup_command(),
            )
            return
        try:
            winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([str(Path(sys.executable).resolve())])
    project_root = Path(__file__).resolve().parents[2]
    return subprocess.list2cmdline(
        [sys.executable, str(project_root / "run_local_app.py")]
    )
