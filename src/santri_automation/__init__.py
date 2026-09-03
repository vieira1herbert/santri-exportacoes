from .config import AutomationConfig, load_config
from .workflow import (
    build_cadastro_produtos_plan,
    build_export_plan,
    build_redirect_plan,
)

__version__ = "2.2.2"

__all__ = [
    "AutomationConfig",
    "__version__",
    "build_cadastro_produtos_plan",
    "build_export_plan",
    "build_redirect_plan",
    "load_config",
]
