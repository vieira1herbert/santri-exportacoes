from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False):
        package_root = Path(sys._MEIPASS) / "santri_automation"
    else:
        package_root = Path(__file__).resolve().parent
    return package_root.joinpath("resources", *parts)
