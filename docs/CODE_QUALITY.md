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

## Validação da v2.2.8

- Black, Ruff e suíte de 150 testes aprovados em 18/09/2026.
- Testes cobrem o botão geral, remoção dos comandos antigos, ordem independente do catálogo e subconjuntos selecionados.
- A execução real não foi iniciada durante a validação automatizada.

## Validação da v2.2.7

- Black, Ruff e suíte de 148 testes aprovados em 18/09/2026.
- Testes novos verificam a espera após confirmar a planilha e a interrupção quando o Santri não libera a interface.
- Homologação operacional ainda necessária; não foram executadas exportações reais durante esta validação.

## Linha de base histórica de qualidade

- Ruff: nenhuma ocorrência na linha de base definida.
- Black: todos os módulos Python formatados.
- Testes: 143 cenários aprovados.
- Dependências: nenhuma vulnerabilidade conhecida identificada pelo `pip-audit`.
- Complexidade média: A, com 4,51 pontos em 374 blocos analisados.

Os maiores pontos de complexidade permanecem concentrados na orquestração do fluxo completo, no agendador, nos diagnósticos, no gerenciamento de releases e no driver visual do Santri. Essas áreas possuem cobertura automatizada e devem ser extraídas gradualmente por caso de uso. Refatorações no driver visual exigem homologação operacional, pois coordenadas, tempos e estados de janela fazem parte do contrato com o ERP.

O índice de manutenibilidade do Radon penaliza módulos extensos e a ausência de comentários. Como o projeto mantém o código sem comentários por decisão interna, esse índice é tratado como indicador de tendência, não como critério isolado de aprovação.
