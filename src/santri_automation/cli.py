from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .config import load_config
from .resource_paths import resource_path
from .runner import DryRunRunner, export_plan_json
from .workflow import build_export_plan, build_redirect_plan


DEFAULT_CONFIG = resource_path("config", "cadastro_produtos.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Planeja a automação do Cadastro de Produtos no Santri."
    )
    parser.add_argument(
        "--company",
        choices=("sol", "horus", "all"),
        default="all",
    )
    parser.add_argument(
        "--action",
        choices=("export", "redirect"),
        required=True,
        help="Exporta pelo Santri ou redireciona os arquivos já gerados.",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        help="Data no formato AAAA-MM-DD.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
    )
    parser.add_argument(
        "--export-plan",
        type=Path,
        help="Pasta opcional para salvar os planos em JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    company_keys = (
        tuple(config.companies)
        if args.company == "all"
        else (args.company,)
    )
    runner = DryRunRunner()
    plan_builder = (
        build_export_plan
        if args.action == "export"
        else build_redirect_plan
    )

    for company_key in company_keys:
        plan = plan_builder(
            config=config,
            company_key=company_key,
            execution_date=args.date,
        )
        print(f"\n=== {plan.company.label} ===")
        runner.run(plan)
        if args.export_plan:
            args.export_plan.mkdir(parents=True, exist_ok=True)
            export_plan_json(
                plan,
                args.export_plan
                / f"cadastro-produtos-{company_key}-{args.action}.json",
            )


if __name__ == "__main__":
    main()
