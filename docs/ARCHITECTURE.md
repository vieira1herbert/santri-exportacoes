# Arquitetura

## Visão geral

O Santri Exportações é uma aplicação desktop local. A interface HTML é
renderizada pelo `pywebview`, enquanto a automação das janelas do Santri é
executada por `pywinauto`.

```text
Painel pywebview
      │
      ▼
DashboardApi
      │
      ├── ExportCatalog ── configurações do usuário
      │
      └── WindowsSantriDriver
              ├── Santri SOL
              ├── Santri HORUS
              ├── arquivos ODS
              └── ShellCadastroProdutos.ps1
```

## Módulos principais

- `desktop_app.py`: cria a janela e expõe a API para o painel.
- `windows_driver.py`: controla o Santri e o sistema de arquivos.
- `catalog.py`: valida e persiste as configurações editáveis.
- `config.py`: carrega as definições fixas das empresas e relatórios.
- `workflow.py`: produz planos de execução testáveis.
- `resources/`: contém configurações iniciais, interface e imagens.

## Persistência

O catálogo distribuído no executável funciona como configuração inicial. As
alterações realizadas pelo usuário são gravadas em:

```text
%LOCALAPPDATA%\Santri Export\export_catalog.json
```

Esse caminho foi preservado para manter compatibilidade com as versões locais
já utilizadas.

## Fluxo do Cadastro de Produtos

1. Abrir o ambiente da empresa selecionada.
2. Selecionar a unidade correta.
3. Exportar a Base sob encomenda.
4. Confirmar a mensagem de sucesso.
5. Remover o filtro de sob encomenda.
6. Selecionar agrupamento por produto.
7. Exportar a Base completa.
8. Redirecionar os dois ODS para suas pastas de leitura.
9. Executar o script de atualização da base.

## Segurança operacional

- Nenhuma senha é versionada.
- A limpeza é limitada às pastas finais de leitura configuradas.
- O script de atualização só é executado dentro do destino do fluxo.
- Uma trava impede duas operações simultâneas pelo painel.
