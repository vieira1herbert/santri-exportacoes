# Arquitetura

## Objetivo

O Santri Exportações é uma aplicação Windows interna que automatiza relatórios do Santri ERP para SOL ATACADISTA e HORUS DISTRIBUIDORA. A arquitetura prioriza previsibilidade operacional, separação de responsabilidades, rastreabilidade e evolução segura.

## Visão por camadas

| Camada | Responsabilidade | Principais módulos |
| --- | --- | --- |
| Apresentação | Exibir estado, receber comandos e proteger alterações pendentes. | resources/ui |
| Fachada desktop | Expor uma API estável ao pywebview e coordenar casos de uso. | desktop_app.py |
| Aplicação | Agendar, executar, retomar, monitorar e auditar workflows. | scheduler.py, executors.py, reliability.py |
| Domínio e configuração | Representar empresas, relatórios, planos, datas e políticas. | config.py, workflow.py, date_ranges.py |
| Infraestrutura | Controlar Windows, arquivos, scripts, persistência, integridade e instância única. | windows_driver.py, catalog.py, security.py, startup.py, single_instance.py |
| Serviços | Encapsular capacidades reutilizáveis sem responsabilidade de interface. | services/system_diagnostics.py, services/operational_monitoring.py |
| Ferramentas técnicas | Inspecionar e exportar planos sem acionar a interface gráfica. | cli.py, runner.py |

O sentido principal das dependências é da apresentação para a fachada, da fachada para aplicação e serviços, e desses componentes para contratos de infraestrutura. A interface não conhece pywinauto nem manipula arquivos diretamente.

## Interface modular

O dashboard.html é apenas o documento semântico. Ele referencia um ponto de entrada de estilos e um ponto de entrada JavaScript.

Os estilos são divididos por área: núcleo visual, inicialização, dashboard, editor, configurações, Sobre, confiabilidade e responsividade.

O JavaScript usa composição explícita:

- DashboardSession mantém somente o estado transitório da tela.
- BridgeClient encapsula a ponte com a API Python.
- PageRouter seleciona o controlador visual da página atual.
- DomRegistry valida a estrutura obrigatória do documento.
- AppearanceService aplica o tema persistido.
- HistoryPresenter formata registros do histórico.
- MonitoringPresenter transforma o estado operacional em indicadores, alertas e séries visuais.
- WorkflowRules concentra regras compartilhadas entre exportações.
- HtmlEscaper protege conteúdo dinâmico antes da inserção no documento.

Elementos exclusivos do Início, como o seletor SOL/HORUS, têm a visibilidade sincronizada antes de cada renderização de rota. Histórico, Configurações, Central e Sobre recebem somente seus próprios componentes.

A página de Configurações usa uma arquitetura administrativa em três níveis: resumo operacional, navegação por áreas e painéis de detalhe. Geral, Ambiente, Monitoramento, Arquivos e retenção, Segurança e Versões compartilham a mesma superfície administrativa. Os campos mantêm identificadores estáveis para preservar a API de persistência, enquanto um estado visual informa alterações ainda não salvas.

A Central tem responsabilidade exclusiva de notificação: contabiliza itens não lidos, filtra por severidade e direciona o usuário ao contexto correto. Diagnósticos, observabilidade, checkpoints, relatórios, backups e gerenciamento de releases permanecem em Configurações.

`NotificationPresenter` e `SettingsAdministrationPresenter` isolam a composição visual dessas áreas. O ponto de entrada coordena navegação e eventos, sem concentrar a marcação específica de cada funcionalidade.

As categorias administrativas seguem semântica nativa de botão e oferecem estados visuais distintos para repouso, passagem do ponteiro, foco por teclado e seleção ativa.

O tema claro deriva suas superfícies das variáveis cinza-azuladas do Grupo SH. Fundo, cartões, controles e estados de interação evitam branco absoluto; elementos de marca e textos sobre a cor primária preservam o contraste necessário.

As marcas institucionais possuem tratamento explícito por tema. O SH preserva o azul do Grupo, a SOL alterna entre verde institucional no tema claro e a versão branca no escuro, e a HORUS reforça o contraste no fundo escuro sem alterar o laranja. Os cartões empresariais usam superfícies verdes e laranjas suaves para manter identidade e legibilidade.

## Fachada e serviços Python

DashboardApi é a fachada pública apresentada ao pywebview. Os nomes dos métodos expostos permanecem estáveis para evitar acoplamento entre JavaScript e implementação.

Responsabilidades independentes são delegadas a serviços. O SystemDiagnostics, por exemplo, cuida das verificações de ambiente, enquanto DashboardApi apenas solicita o resultado e o entrega à interface.

OperationalMonitoring consolida relatórios persistidos, histórico, agendamentos, saúde e segurança. O serviço calcula indicadores de 30 dias, evolução diária, desempenho por workflow e alertas de agendamento sem depender da interface.

Novas funcionalidades devem preferir um serviço ou executor próprio. A fachada não deve acumular lógica de automação visual.

## Extensão por exportação

WorkflowExecutor define o contrato de execução. ExecutorRegistry resolve a implementação correta pelo identificador do workflow.

Cada nova exportação deve:

1. possuir configuração validada no catálogo;
2. implementar um executor coeso;
3. manter cliques específicos dentro do driver;
4. emitir etapas nomeadas para checkpoint e auditoria;
5. possuir testes de plano, execução e falha;
6. atualizar FILES.md, ARCHITECTURE.md e CHANGELOG.md.

## Fluxos existentes

### Cadastro de Produtos

1. Abrir e maximizar somente a janela principal do Santri.
2. Selecionar a unidade definida para a empresa.
3. Exportar Base sob encomenda e confirmar o sucesso.
4. Remover o filtro de sob encomenda.
5. Selecionar agrupamento por produto.
6. Exportar Base completa e confirmar o sucesso.
7. Redirecionar os dois ODS de forma transacional.
8. Executar o script de atualização da base.

### Transferências

1. Resolver período automático ou personalizado.
2. Abrir o relatório mantendo sua janela interna no tamanho original.
3. Aplicar o período e o modo analítico.
4. Exportar, redirecionar e atualizar a base.

### Estoque Disponível

1. Abrir Valor do estoque e selecionar as empresas autorizadas.
2. Aplicar opcionalmente Não em Ativo imobilizado e Uso e consumo.
3. Confirmar a operação de longa duração.
4. Gerar Dados por empresa - modelo 2.
5. Redirecionar para o destino mensal.
6. Executar ShellEstoqueDisp.ps1 no contexto esperado.

## Persistência e confiabilidade

O catálogo distribuído no executável serve como configuração inicial. Alterações do usuário são gravadas em %LOCALAPPDATA%\Santri Export\export_catalog.json.

A persistência usa gravação atômica, sincronização entre threads e backups rotativos. Redirecionamentos validam os arquivos antes da substituição e restauram o estado anterior em caso de falha.

Cada execução recebe identificador, sessão, etapas, tentativas, arquivos, falhas e evidências. Checkpoints permitem continuar sem repetir etapas concluídas.

## Monitoramento operacional

A v1.5 acrescenta uma camada somente de leitura sobre os dados operacionais persistidos. Taxas e durações são calculadas pelos relatórios de execução, enquanto alertas de agendamento confrontam horários vencidos com slots registrados e eventos auditados.

## Agenda profissional

A v1.6 mantém a execução Windows no núcleo existente e separa planejamento de execução. `ScheduleCenter` produz calendário, fila e previsões sem alterar o catálogo. `WorkflowScheduler` reivindica cada slot uma única vez e ordena trabalhos simultâneos pela prioridade persistida. Exceções são datas ISO explícitas; checkpoints registram as etapas concluídas e o limite de tentativas é aplicado pelo executor de confiabilidade.

Parâmetros temporários são copiados sobre a definição carregada apenas na memória da sessão. O catálogo não é salvo e destinos temporários continuam limitados à raiz da empresa.

## Homologação e distribuição

A v1.7 seleciona Produção ou Homologação antes da construção do catálogo. Cada ambiente possui catálogo, integridade, histórico, relatórios e backups próprios. `ReleaseManager` concentra consulta, preferências, notas, preparação, verificação e ativação, mantendo operações de rede fora da fachada desktop.

## Plataforma modular v2.0

`WorkflowBlueprintRegistry` descreve executores, parâmetros, saídas e etapas em uma camada de domínio que não conhece detalhes do Windows. `WorkflowSimulator` homologa configurações sem abrir ou controlar o Santri. Os executores existentes permanecem como adaptadores da automação visual.

`PersistentExecutionQueue` armazena os itens em JSON atômico, recupera execuções interrompidas como aguardando e permite cancelamento cooperativo entre etapas. `WorkflowVersionStore` mantém snapshots limitados e verificados por SHA-256. Evidências dos artefatos são anexadas ao histórico e ao resultado da execução.

Uma atualização percorre: consultar release oficial → criar backup → baixar manifesto → validar versão → baixar executável → conferir SHA-256 → registrar pacote versionado → ativar por confirmação. O executável em uso nunca é sobrescrito. O atalho passa a apontar para a release verificada, permitindo retornar a um pacote preservado.

## Estabilização operacional v2.1

`ExecutionRequestPlanner` prepara a solicitação antes da automação visual. O serviço valida a ação, resolve workflows, limita timeout e tentativas, aplica parâmetros temporários sobre cópias e restringe destinos ao escopo da empresa. `DashboardApi` permanece como fachada e recebe um pedido preparado, enquanto os executores e o `WindowsSantriDriver` mantêm o contrato homologado.

O pipeline de integração contínua executa a mesma linha de base usada localmente: Ruff, Black, compilação, testes e auditoria de dependências. Uma release não avança para o build quando qualquer uma dessas verificações falha.

## Observabilidade operacional v2.2

`ExecutionObservability` lê somente os relatórios autenticados mantidos por `ReliabilityCenter`. A camada agrupa eventos por etapa, calcula duração entre o primeiro e o último evento, conta retentativas e resultados, normaliza assinaturas de falha e relaciona os artefatos ao manifesto SHA-256. A área Monitoramento, dentro de Configurações, apresenta essa projeção sem modificar relatórios nem transmitir telemetria.

Os indicadores são reconstruíveis: relatórios são a fonte de verdade, `OperationalMonitoring` compõe a visão e `MonitoringPresenter` apenas formata os dados escapados. Falhas de infraestrutura registradas apenas no nível da sessão continuam visíveis quando não existe uma etapa operacional mais específica.

O instalador Inno Setup usa privilégios do usuário, instala em `%LOCALAPPDATA%`, cria atalhos e registra desinstalação. A assinatura Authenticode permanece condicional ao certificado corporativo.

Antes de cada fluxo, SystemDiagnostics executa um preflight específico para a ação. Sessão Windows, atalho, pasta local, destinos e atualizadores são obrigatórios conforme a etapa. O Santri fechado é informativo porque o driver possui abertura automática.

A retenção do histórico preserva a âncora da cadeia autenticada. A limpeza de relatórios, checkpoints, evidências e pacotes de suporte permanece limitada à pasta local de confiabilidade e aos prazos salvos pelo usuário.

## Segurança

A v1.4 aplica defesa em profundidade. `FileIntegrityService` autentica dados persistidos com HMAC-SHA256 e protege a chave local com DPAPI. O histórico usa encadeamento autenticado, permitindo detectar alteração ou reordenação. `WindowsSecurityService` expõe o estado dos controles à interface, e `UpdateScriptPolicy` concentra a autorização dos atualizadores externos.

O build produz uma lista CycloneDX de componentes e um manifesto que associa versão, commit e SHA-256. A assinatura Authenticode é realizada somente quando o ambiente corporativo fornece o caminho do SignTool e a impressão digital de um certificado instalado, sem segredo no repositório.

- Nenhuma senha é armazenada no repositório ou catálogo.
- Conteúdo dinâmico da interface é escapado.
- A política de conteúdo bloqueia rede, objetos, formulários e scripts não locais.
- Limpezas são restritas aos destinos validados.
- Scripts só são executados no destino autorizado do workflow.
- Dados sensíveis são removidos do histórico e dos pacotes de suporte.
- A aplicação impede operações e instâncias concorrentes.
- Evidências visuais permanecem locais até revisão humana.

## Princípios de engenharia

- Responsabilidade única: UI, diagnóstico, catálogo, execução e driver têm limites próprios.
- Aberto para extensão: novos executores entram pelo registro sem alterar fluxos existentes.
- Substituição: executores obedecem ao mesmo contrato operacional.
- Segregação: a interface acessa apenas os métodos necessários da fachada.
- Inversão: DashboardApi recebe catálogo, driver, loader e registro por dependência.
- Falha antecipada: configurações, DOM e arquivos são validados antes de operações destrutivas.
- Compatibilidade: contratos públicos e dados persistidos evoluem sem quebrar instalações existentes.

## Qualidade

As verificações incluem Ruff, Black, compilação Python, testes funcionais, testes de segurança, testes arquiteturais e acompanhamento de complexidade pelo Radon. A compatibilidade mínima está fixada em Python 3.11. O empacotamento também é executado por Python, sem arquivos de build específicos de shell versionados. O executável só deve ser publicado depois que a suíte completa e o empacotamento forem concluídos sem erro. A linha de base e os riscos conhecidos estão registrados em `docs/CODE_QUALITY.md`.
