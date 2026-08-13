# Mapa de arquivos

Este documento registra a responsabilidade de cada arquivo mantido no projeto. Toda inclusão, remoção ou mudança estrutural deve atualizar este mapa, o CHANGELOG.md e o docs/ARCHITECTURE.md.

## Raiz

| Arquivo | Responsabilidade |
| --- | --- |
| .editorconfig | Padroniza codificação, indentação e finais de linha entre editores. |
| .gitattributes | Normaliza o tratamento de arquivos pelo Git. |
| .gitignore | Exclui builds, caches e dados locais do versionamento. |
| CHANGELOG.md | Mantém o histórico funcional e técnico das versões. |
| SECURITY.md | Define suporte, comunicação de vulnerabilidades e controles obrigatórios. |
| README.md | Apresenta produto, instalação, execução, segurança e contribuição. |
| pyproject.toml | Define metadados, dependências, pacote Python e recursos embarcados. |
| run_local_app.py | Inicializa o aplicativo pelo código-fonte ou executável. |
| build_app.py | Gera o executável e atualiza o atalho usando somente Python. |

## Automação e documentação

| Arquivo | Responsabilidade |
| --- | --- |
| .github/workflows/ci.yml | Executa verificações automatizadas do repositório. |
| .github/workflows/codeql.yml | Executa análise estática de segurança do código Python. |
| .github/workflows/dependency-review.yml | Bloqueia dependências vulneráveis introduzidas em pull requests. |
| .github/dependabot.yml | Agenda atualizações controladas de dependências e GitHub Actions. |
| docs/ARCHITECTURE.md | Explica camadas, fluxos, dependências e decisões arquiteturais. |
| docs/FILES.md | Mapeia cada arquivo e sua função no produto. |
| docs/THREAT_MODEL.md | Documenta ativos, fronteiras, ameaças, mitigações e riscos residuais. |
| docs/SECURITY_HOMOLOGATION.md | Define evidências e aprovações exigidas para liberar a v1.4. |

## Pacote Python

| Arquivo | Responsabilidade |
| --- | --- |
| src/santri_automation/__init__.py | Expõe a versão pública do pacote. |
| src/santri_automation/__main__.py | Permite executar o pacote como módulo. |
| src/santri_automation/cli.py | Implementa comandos de linha e diagnóstico técnico. |
| src/santri_automation/config.py | Converte configuração fixa em objetos tipados. |
| src/santri_automation/catalog.py | Valida, persiste, restaura e versiona configurações editáveis. |
| src/santri_automation/date_ranges.py | Normaliza e resolve períodos de relatórios. |
| src/santri_automation/desktop_app.py | Fachada entre interface, casos de uso e pywebview. |
| src/santri_automation/executors.py | Contrato e executores específicos de cada exportação. |
| src/santri_automation/reliability.py | Checkpoints, notificações, evidências, relatórios e suporte. |
| src/santri_automation/resource_paths.py | Resolve recursos no código-fonte e no executável. |
| src/santri_automation/runner.py | Exibe e exporta os planos da ferramenta técnica de linha de comando. |
| src/santri_automation/scheduler.py | Dispara horários pendentes sem duplicidade. |
| src/santri_automation/security.py | Protege integridade, identidade, releases e execução de atualizadores. |
| src/santri_automation/single_instance.py | Impede duas instâncias simultâneas. |
| src/santri_automation/startup.py | Gerencia a inicialização junto ao Windows. |
| src/santri_automation/windows_driver.py | Isola janelas, cliques, arquivos e scripts do Windows/Santri. |
| src/santri_automation/workflow.py | Constrói planos declarativos de execução. |
| src/santri_automation/services/__init__.py | Identifica a camada de serviços internos. |
| src/santri_automation/services/system_diagnostics.py | Verifica Windows, armazenamento, atalhos, destinos e scripts. |
| src/santri_automation/services/operational_monitoring.py | Calcula indicadores, tendências, alertas e o resumo técnico operacional. |

## Configurações embarcadas

| Arquivo | Responsabilidade |
| --- | --- |
| src/santri_automation/resources/config/cadastro_produtos.json | Empresas, unidades, filtros e caminhos fixos. |
| src/santri_automation/resources/config/export_catalog.json | Catálogo inicial de exportações e preferências. |

## Interface JavaScript

| Arquivo | Responsabilidade |
| --- | --- |
| src/santri_automation/resources/ui/dashboard.html | Estrutura semântica e pontos de montagem da interface. |
| src/santri_automation/resources/ui/scripts/app.js | Compõe dependências, rotas, orquestração e visibilidade dos elementos de cada página. |
| src/santri_automation/resources/ui/scripts/core/appearance-service.js | Aplica o tema persistido. |
| src/santri_automation/resources/ui/scripts/core/bridge-client.js | Encapsula o acesso à API Python. |
| src/santri_automation/resources/ui/scripts/core/dashboard-session.js | Estado transitório da sessão. |
| src/santri_automation/resources/ui/scripts/core/dom-registry.js | Resolve elementos obrigatórios e falha cedo. |
| src/santri_automation/resources/ui/scripts/core/page-router.js | Mapeia páginas para renderizadores. |
| src/santri_automation/resources/ui/scripts/features/history/history-presenter.js | Formata e protege registros do histórico. |
| src/santri_automation/resources/ui/scripts/features/monitoring/monitoring-presenter.js | Apresenta saúde, desempenho, evolução e alertas operacionais. |
| src/santri_automation/resources/ui/scripts/features/workflows/workflow-rules.js | Regras de identificação e resultado dos workflows. |
| src/santri_automation/resources/ui/scripts/shared/html-escaper.js | Escapa dados dinâmicos antes da inserção no HTML. |

## Estilos

| Arquivo | Responsabilidade |
| --- | --- |
| src/santri_automation/resources/ui/styles/app.css | Importa módulos na ordem correta. |
| src/santri_automation/resources/ui/styles/core.css | Tokens, temas, reset e estrutura global. |
| src/santri_automation/resources/ui/styles/startup.css | Experiência de inicialização. |
| src/santri_automation/resources/ui/styles/dashboard.css | Navegação, empresas, indicadores e tabela principal. |
| src/santri_automation/resources/ui/styles/editor.css | Formulários, modal, progresso e confirmações. |
| src/santri_automation/resources/ui/styles/settings.css | Painel administrativo, navegação de categorias, diagnóstico e controles de aparência. |
| src/santri_automation/resources/ui/styles/about.css | Apresentação institucional e autoria. |
| src/santri_automation/resources/ui/styles/reliability.css | Histórico, diagnósticos, backups e confiabilidade. |
| src/santri_automation/resources/ui/styles/monitoring.css | Indicadores, gráficos, alertas e desempenho operacional da v1.5. |
| src/santri_automation/services/schedule_center.py | Monta calendário, fila priorizada e previsões da agenda. |
| src/santri_automation/resources/ui/scripts/features/scheduling/schedule-presenter.js | Apresenta a central de agendamentos profissionais. |
| src/santri_automation/resources/ui/styles/scheduling.css | Isola a identidade visual do calendário e da fila. |
| src/santri_automation/services/release_manager.py | Controla ambientes, canais, consulta, backup, validação, ativação e reversão de releases. |
| src/santri_automation/resources/ui/scripts/features/releases/release-presenter.js | Apresenta a central de homologação e atualizações. |
| src/santri_automation/resources/ui/styles/releases.css | Estilização isolada da distribuição controlada. |
| src/santri_automation/resources/config/CHANGELOG.md | Notas das versões empacotadas no executável. |
| installer/SantriExportacoes.iss | Definição do instalador corporativo Windows. |
| build_installer.py | Compila o instalador com Inno Setup 6. |
| .github/workflows/release.yml | Pipeline manual de teste, auditoria, executável e instalador. |
| src/santri_automation/resources/ui/styles/responsive.css | Adaptações por largura e preferência de movimento. |

## Identidade visual

| Arquivo | Responsabilidade |
| --- | --- |
| src/santri_automation/resources/ui/assets/sh-app-icon.ico | Ícone do executável Windows. |
| src/santri_automation/resources/ui/assets/sh-app-icon.png | Marca SH usada na interface. |
| src/santri_automation/resources/ui/assets/logo-sol.webp | Identidade da SOL ATACADISTA. |
| src/santri_automation/resources/ui/assets/logo-horus.png | Identidade da HORUS DISTRIBUIDORA. |

## Testes

| Arquivo | Responsabilidade |
| --- | --- |
| tests/test_workflow.py | Regras de negócio, automação, persistência, segurança e interface. |
| tests/test_architecture.py | Modularização, camadas e codificação dos recursos. |
| tests/test_security.py | Valida integridade, auditoria, atualização restrita, sanitização e release. |
| tests/test_monitoring.py | Valida métricas, alertas, preflight, resumo técnico e retenção da v1.5. |
| tests/test_scheduling.py | Valida prioridades, exceções, previsões e calendário da v1.6. |
| tests/test_releases.py | Valida ambientes, backup, hash, preparação e notas da v1.7. |
