# Arquitetura

## Objetivo

O Santri Exportações é uma aplicação Windows interna que automatiza relatórios do Santri ERP para SOL ATACADISTA e HORUS DISTRIBUIDORA. A arquitetura prioriza previsibilidade operacional, separação de responsabilidades, rastreabilidade e evolução segura.

## Visão por camadas

| Camada | Responsabilidade | Principais módulos |
| --- | --- | --- |
| Apresentação | Exibir estado, receber comandos e proteger alterações pendentes. | resources/ui |
| Fachada desktop | Expor uma API estável ao pywebview e coordenar casos de uso. | desktop_app.py |
| Aplicação | Agendar, executar, retomar e auditar workflows. | scheduler.py, executors.py, reliability.py |
| Domínio e configuração | Representar empresas, relatórios, planos, datas e políticas. | config.py, workflow.py, date_ranges.py |
| Infraestrutura | Controlar Windows, arquivos, scripts, persistência e instância única. | windows_driver.py, catalog.py, startup.py, single_instance.py |
| Serviços | Encapsular capacidades reutilizáveis sem responsabilidade de interface. | services/system_diagnostics.py |
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
- WorkflowRules concentra regras compartilhadas entre exportações.
- HtmlEscaper protege conteúdo dinâmico antes da inserção no documento.

Elementos exclusivos da Central, como o seletor SOL/HORUS, têm a visibilidade sincronizada antes de cada renderização de rota. Histórico, Configurações, Confiabilidade e Sobre recebem somente seus próprios componentes.

A página de Configurações usa uma arquitetura administrativa em três níveis: resumo operacional, navegação por categorias e formulários de detalhe. Os campos mantêm identificadores estáveis para preservar a API de persistência, enquanto um estado visual informa alterações ainda não salvas.

## Fachada e serviços Python

DashboardApi é a fachada pública apresentada ao pywebview. Os nomes dos métodos expostos permanecem estáveis para evitar acoplamento entre JavaScript e implementação.

Responsabilidades independentes são delegadas a serviços. O SystemDiagnostics, por exemplo, cuida das verificações de ambiente, enquanto DashboardApi apenas solicita o resultado e o entrega à interface.

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

## Segurança

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

As verificações incluem compilação Python, testes funcionais, testes de segurança e testes arquiteturais. O empacotamento também é executado por Python, sem arquivos de build específicos de shell versionados. O executável só deve ser publicado depois que a suíte completa e o empacotamento forem concluídos sem erro.
