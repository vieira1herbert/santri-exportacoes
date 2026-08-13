from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StageDefinition:
    key: str
    name: str
    order: int
    requires_destination: bool = False


@dataclass(frozen=True)
class WorkflowBlueprint:
    workflow_id: str
    name: str
    executor: str
    outputs: int
    parameters: tuple[str, ...]
    stages: tuple[StageDefinition, ...]


class WorkflowBlueprintRegistry:
    def __init__(self, blueprints: list[WorkflowBlueprint]) -> None:
        self._blueprints = {item.workflow_id: item for item in blueprints}

    def get(self, workflow_id: str) -> WorkflowBlueprint | None:
        return self._blueprints.get(workflow_id)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                **asdict(item),
                "stages": [asdict(stage) for stage in item.stages],
            }
            for item in self._blueprints.values()
        ]


def build_blueprint_registry() -> WorkflowBlueprintRegistry:
    stages = (
        StageDefinition("export", "Exportar pelo Santri", 1),
        StageDefinition("redirect", "Redirecionar arquivos", 2, True),
        StageDefinition("update", "Atualizar base", 3, True),
    )
    return WorkflowBlueprintRegistry(
        [
            WorkflowBlueprint(
                "cadastro_produtos",
                "Cadastro de Produtos",
                "CadastroProdutosExecutor",
                2,
                ("destination", "filename_prefix"),
                stages,
            ),
            WorkflowBlueprint(
                "transfer_ncias",
                "Transferências",
                "TransferenciasExecutor",
                1,
                ("destination", "filename_prefix", "date_range"),
                stages,
            ),
            WorkflowBlueprint(
                "estoque_disponivel",
                "Estoque Disponível",
                "EstoqueDisponivelExecutor",
                1,
                ("destination", "filename_prefix", "include_asset_consumption"),
                stages,
            ),
        ]
    )
