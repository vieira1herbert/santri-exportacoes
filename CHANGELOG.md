# Changelog

## 1.3.0 — 2026-08-12

- Automação completa de Estoque Disponível para SOL e HORUS.
- Seleção automática de todas as empresas autorizadas no relatório.
- Configuração para marcar Ativo imobilizado e Uso e consumo como Não ou preservar os filtros do Santri.
- Destino mensal editável separadamente em cada empresa.
- Exportação no formato Dados por empresa - modelo 2.
- Inicialização protegida contra painel vazio e ponte do agente restrita aos comandos autorizados.
- Execução silenciosa dos scripts de atualização, sem bloqueio por comandos pause.
- Janela principal do Santri preservada maximizada e relatórios mantidos no tamanho original.
- Limpeza transacional da pasta de leitura, com backup e restauração em falhas.
- Atualização da base por `ShellEstoqueDisp.ps1`.
- Confirmação semântica das mensagens de processamento e sucesso do Santri.

## 1.2.0 — 2026-08-03

- Central de Confiabilidade com notificações persistentes.
- Diagnóstico aprofundado de atalhos, destinos, scripts, disco e permissões.
- Captura automática da tela e relatório HTML/JSON em falhas.
- Retentativas automáticas para falhas temporárias.
- Checkpoints por etapa e retomada de execuções interrompidas.
- Linha do tempo detalhada e relatório final de cada execução.
- Criação e restauração segura de backups pelo painel.
- Pacote de suporte sanitizado com diagnósticos, relatórios e evidências.

## 1.1.1 — 2026-08-03

- Automação completa da exportação de Transferências para SOL e HORUS.
- Período automático de Transferências entre o primeiro dia do mês anterior e a data atual.
- Período personalizado editável nas configurações de cada exportação.
- Pesquisa de empresas pela chave com confirmação por Enter e seleção automática da unidade correta.
- Preenchimento confiável das datas a partir do primeiro caractere do campo no Santri.
- Retorno automático à tela inicial do Santri após cada relatório, preservando a janela maximizada.
- Redirecionamento e atualização das bases de Transferências validados nas duas empresas.
- Confirmações internas padronizadas com a identidade visual do aplicativo.
- Correções de alinhamento em indicadores, ícones de ação e status de exportações em construção.
- Seletores de exportações redesenhados com marcação geral no cabeçalho da tabela.
- Textos auxiliares nos comandos em lote para esclarecer exportação, redirecionamento e atualização.
- Revisão visual das telas de gestão, histórico e configurações gerais.

## 1.1.0 — 2026-08-03

- Histórico corporativo persistente com filtros e exportação CSV.
- Agendamentos por dia e horário, modo desligado e recuperação de horário perdido.
- Execução completa em um clique e inicialização automática com o Windows.
- Instância única, backups rotativos e gravação sincronizada do catálogo.
- Redirecionamento transacional com restauração dos arquivos anteriores.
- Motor registrável de executores para novas exportações.
- Replicação de exportações em construção entre SOL e HORUS.
- Diagnóstico operacional e painel executivo com taxa de sucesso.
- Sanitização de informações sensíveis na auditoria.
- Pipeline de testes e compilação versionada no GitHub Actions.

## 1.0.0 — 2026-07-30

- Aplicativo local separado integralmente do protótipo hospedado no Sites.
- Painéis independentes para SOL e HORUS.
- Fluxo completo do Cadastro de Produtos.
- Ações de exportar, redirecionar e atualizar a base.
- Configurações persistentes por exportação.
- Identidade visual SH e nome Santri Exportações.
- Estrutura de repositório, testes e integração contínua para GitHub.
