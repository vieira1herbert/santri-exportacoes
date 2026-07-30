from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


ControlType = Literal["select", "radio"]


@dataclass(frozen=True)
class FilterRule:
    tab: str
    field: str
    control: ControlType
    value: str


@dataclass(frozen=True)
class ExportDefinition:
    key: str
    name: str
    filename_template: str
    destination_subfolder: str
    filters: tuple[FilterRule, ...]


@dataclass(frozen=True)
class WorkflowDefinition:
    key: str
    name: str
    window_title_contains: str
    menu_path: tuple[str, ...]
    exports: tuple[ExportDefinition, ...]


@dataclass(frozen=True)
class CompanyDefinition:
    key: str
    label: str
    filename_prefix: str
    shortcut: Path
    credential_target: str
    network_root: Path
    postprocess_command: str | None


@dataclass(frozen=True)
class AutomationConfig:
    workflow: WorkflowDefinition
    companies: dict[str, CompanyDefinition]


def _expand_path(value: str) -> Path:
    return Path(os.path.expandvars(value))


def load_config(path: Path) -> AutomationConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))

    exports = tuple(
        ExportDefinition(
            key=item["key"],
            name=item["name"],
            filename_template=item["filename_template"],
            destination_subfolder=item["destination_subfolder"],
            filters=tuple(FilterRule(**rule) for rule in item["filters"]),
        )
        for item in raw["workflow"]["exports"]
    )
    workflow = WorkflowDefinition(
        key=raw["workflow"]["key"],
        name=raw["workflow"]["name"],
        window_title_contains=raw["workflow"]["window_title_contains"],
        menu_path=tuple(raw["workflow"]["menu_path"]),
        exports=exports,
    )
    companies = {
        key: CompanyDefinition(
            key=key,
            label=item["label"],
            filename_prefix=item["filename_prefix"],
            shortcut=_expand_path(item["shortcut"]),
            credential_target=item["credential_target"],
            network_root=_expand_path(item["network_root"]),
            postprocess_command=item["postprocess_command"],
        )
        for key, item in raw["companies"].items()
    }
    return AutomationConfig(workflow=workflow, companies=companies)
