from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFINITION = ROOT / "installer" / "SantriExportacoes.iss"


def locate_compiler() -> Path | None:
    candidates = [
        Path(value)
        for value in (
            os.environ.get("SANTRI_ISCC", ""),
            shutil.which("iscc.exe") or "",
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe"),
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        )
        if value
    ]
    return next((path for path in candidates if path.is_file()), None)


def main() -> int:
    compiler = locate_compiler()
    if compiler is None:
        raise FileNotFoundError("Inno Setup 6 não encontrado. Defina SANTRI_ISCC.")
    subprocess.run([compiler, str(DEFINITION)], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
