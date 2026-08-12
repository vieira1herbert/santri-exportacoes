# Changelog

## 1.3.0 — 2026-08-12

- Automação completa de Estoque Disponível para SOL e HORUS.
- Seleção automática de todas as empresas autorizadas no relatório.
- Configuração para marcar Ativo imobilizado e Uso e consumo como Não ou preservar os filtros do Santri.
- Destino mensal editável separadamente em cada empresa.
- Exportação no formato Dados por empresa - modelo 2.
- Inicialização protegida contra painel vazio e ponte do agente restrita aos comandos autorizados.
- Execução dos arquivos PowerShell originais via `-File`, preservando `$PSScriptRoot` e respondendo automaticamente aos comandos pause.
- Janela principal do Santri preservada maximizada e relatórios mantidos no tamanho original.
- Limpeza transacional da pasta de leitura, com backup e restauração em falhas.
- Atualização da base por `ShellEstoqueDisp.ps1`.
- Confirmação semântica das mensagens de processamento e sucesso do Santri.
- Tela Sobre simplificada com autoria destacada e acesso seguro ao repositório oficial.
- Tela de inicialização redesenhada com identidade corporativa, status do agente e empresas configuradas.
- Janela com dimensão mínima operacional, tabela responsiva e barras de rolagem visuais removidas.
- Alternância persistente entre os temas claro e escuro, com superfícies e contrastes revisados em todo o aplicativo.
- Quebra responsiva de nomes, composições e resultados longos sem sobreposição entre colunas.
- Indicador de rolagem próprio do Grupo SH no lugar das barras nativas do navegador.
- Confirmação para salvar ou descartar alterações ao sair das Configurações.
- Autoria exibida uma única vez no encerramento da tela Sobre.
- Editor de exportações aberto em janela modal independente do painel principal.
- Proteção geral de alterações pendentes em Configurações e no editor de exportações.
- Interface separada em HTML semântico, módulos JavaScript e oito módulos de estilo por responsabilidade.
- Estado, roteamento, ponte Python, DOM, aparência, histórico e regras de workflows encapsulados em classes.
- Diagnóstico do ambiente extraído da fachada para um serviço Python independente.
- Política de conteúdo reforçada para carregar somente estilos e módulos locais.
- Testes arquiteturais adicionados para impedir retorno ao dashboard monolítico e detectar problemas de codificação.
- Mapa permanente de responsabilidades criado em docs/FILES.md.
- Empacotamento migrado para Python e remoção da pasta de build PowerShell do repositório.
- Artefatos regeneráveis removidos do ambiente local e classe de pós-processamento sem uso eliminada.
- Seletor SOL/HORUS restrito à Central de exportações e ocultado nas demais telas.

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
