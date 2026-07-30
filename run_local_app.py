from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from santri_automation.desktop_app import main


if __name__ == "__main__":
    main()
