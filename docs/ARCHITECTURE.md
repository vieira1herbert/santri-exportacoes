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
      ├── ReliabilityCenter ── evidências, relatórios e recuperação
      │       ├── NotificationCenter
      │       ├── ExecutionSession
      │       └── checkpoints por etapa
      ├── ExecutorRegistry ── executores por exportação
      └── WindowsSantriDriver
              ├── Santri SOL
              ├── Santri HORUS
              ├── arquivos ODS
              └── scripts de atualização das bases
```

## Módulos principais

- `desktop_app.py`: cria a janela e expõe a API para o painel.
- `windows_driver.py`: controla o Santri e o sistema de arquivos.
- `executors.py`: registra e executa fluxos independentes por relatório.
- `catalog.py`: valida e persiste as configurações editáveis.
- `scheduler.py`: identifica e executa horários pendentes sem duplicidade.
- `reliability.py`: centraliza notificações, diagnósticos, evidências,
  retentativas, checkpoints, relatórios e pacotes de suporte.
- `single_instance.py`: impede duas instâncias simultâneas.
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

O catálogo possui gravação atômica, sincronização entre threads e vinte
backups rotativos. Os redirecionamentos mantêm dez sessões de backup por
empresa fora das pastas de leitura.

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

## Fluxo do Estoque Disponível

1. Abrir Relatórios, Estoque e Valor do estoque.
2. Selecionar todas as empresas autorizadas.
3. Aplicar opcionalmente Sim em Ativo imobilizado e Uso e consumo.
4. Processar e confirmar a operação de longa duração.
5. Gerar a planilha em Dados por empresa - modelo 2.
6. Salvar o ODS com o prefixo configurado.
7. Limpar e substituir a planilha na pasta de leitura do mês.
8. Executar `ShellEstoqueDisp.ps1` no destino mensal configurado.

## Segurança operacional

- Nenhuma senha é versionada.
- A limpeza é limitada às pastas finais de leitura configuradas.
- O script de atualização só é executado dentro do destino do fluxo.
- Uma trava impede duas operações simultâneas pelo painel.
- Uma trava global impede duas instâncias do aplicativo.
- O redirecionamento prepara e valida todos os arquivos antes da substituição.
- Em caso de falha, os arquivos anteriores são restaurados automaticamente.
- Campos sensíveis são removidos do histórico de auditoria.
- Falhas capturam evidências visuais e geram relatórios sanitizados.
- Retentativas são limitadas a erros classificados como temporários.
- Etapas concluídas são persistidas para retomada sem repetição.

## Confiabilidade da versão 1.2

Cada execução recebe um identificador único e uma sessão persistente. A sessão
registra início, tentativas, etapas concluídas, arquivos, falhas e evidências.
O relatório final é gravado em JSON para processamento e em HTML para leitura.

Falhas temporárias podem ser tentadas novamente até duas vezes. Uma falha
definitiva preserva o checkpoint, permitindo que o operador retome a execução
a partir da primeira etapa ainda não concluída.

As notificações, relatórios, checkpoints, evidências e pacotes de suporte são
armazenados no perfil local do usuário, fora do executável e do repositório.
O pacote de suporte sanitiza textos e não anexa screenshots automaticamente;
as evidências visuais permanecem locais para revisão antes do compartilhamento.
