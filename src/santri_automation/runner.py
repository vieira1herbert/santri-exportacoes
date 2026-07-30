from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from .workflow import ExecutionPlan, Step


class DryRunRunner:
    def run(self, plan: ExecutionPlan) -> None:
        for index, step in enumerate(plan.steps, start=1):
            params = (
                " " + json.dumps(step.parameters, ensure_ascii=False)
                if step.parameters
                else ""
            )
            print(f"{index:02d}. [{step.action}] {step.description}{params}")


class LocalPostprocessor:
    def run(self, step: Step) -> None:
        command = step.parameters.get("command")
        if not command:
            raise RuntimeError(
                "O comando de pós-processamento ainda não foi configurado."
            )
        subprocess.run(command, check=True, shell=False)


def export_plan_json(plan: ExecutionPlan, destination: Path) -> None:
    payload = {
        "action": plan.action,
        "company": asdict(plan.company),
        "steps": [asdict(step) for step in plan.steps],
        "expected_files": [str(path) for path in plan.expected_files],
    }
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
