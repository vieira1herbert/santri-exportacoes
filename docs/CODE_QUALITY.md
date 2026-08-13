# Qualidade de código

Este projeto adota uma linha de base automatizada para legibilidade, compatibilidade e manutenção sem alterar os cliques homologados do Santri ERP.

## Padrão obrigatório

- Python 3.11 como versão mínima de compatibilidade.
- Black para formatação determinística.
- Ruff para imports, erros objetivos, modernização segura e boas práticas.
- Unittest para comportamento funcional, arquitetura, segurança e interface.
- Radon para acompanhamento de complexidade ciclomática e manutenibilidade.
- `git diff --check` para impedir espaços inválidos e conflitos de final de linha.

## Execução local

```powershell
python -m pip install -e ".[quality]"
python -m ruff check src tests
python -m black --check src tests
python -m unittest discover -s tests -v
python -m radon cc src/santri_automation -a -s
python -m radon mi src/santri_automation -s
```

## Resultado da auditoria da v2.0.1

- Ruff: nenhuma ocorrência na linha de base definida.
- Black: todos os módulos Python formatados.
- Testes: 126 cenários aprovados.
- Complexidade média: A, com 4,59 pontos em 349 blocos analisados.

Os maiores pontos de complexidade permanecem concentrados na orquestração do fluxo completo, no agendador, nos diagnósticos, no gerenciamento de releases e no driver visual do Santri. Essas áreas possuem cobertura automatizada e devem ser extraídas gradualmente por caso de uso. Refatorações no driver visual exigem homologação operacional, pois coordenadas, tempos e estados de janela fazem parte do contrato com o ERP.

O índice de manutenibilidade do Radon penaliza módulos extensos e a ausência de comentários. Como o projeto mantém o código sem comentários por decisão interna, esse índice é tratado como indicador de tendência, não como critério isolado de aprovação.
