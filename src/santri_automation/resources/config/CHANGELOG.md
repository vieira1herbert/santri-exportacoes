# Notas das versões

## 2.2.9 — Transferências da HORUS

- Corrigida a abertura do relatório de Transferências na HORUS, cuja estrutura de menu não possui o item WMS exibido na SOL.
- A automação deixa de abrir a função vizinha que apresentava `Acesso não permitido`.

## 2.2.8 — Execução geral das selecionadas

- Um único botão `Executar Selecionadas` executa Exportar, Redirecionar e Atualizar Base de cada fluxo marcado.
- Ordem do lote: Cadastro de Produtos, Transferências e Estoque Disponível.

## 2.2.7 — Espera entre as exportações

- O Santri precisa liberar a interface após gerar cada planilha antes que o aplicativo configure a próxima base ou encerre o relatório.
- Janelas desabilitadas e avisos de processamento impedem o avanço prematuro.

## 2.2.6 — Encerramento confiável dos relatórios

- O aplicativo aguarda a liberação real do Santri antes de fechar a tela do relatório.
- Um segundo fechamento controlado trata comandos eventualmente ignorados durante a finalização da planilha.

## 2.2.5 — Filtros corretos do estoque

- `Ativo imobilizado` e `Uso e consumo` passam a ser identificados na segunda coluna da grade de filtros atualizada.
- Os campos vizinhos `Ativo` e `Revenda` deixam de ser alterados pela automação.

## 2.2.4 — Processamento seguro do estoque

- A aba `Resultado` somente é aberta depois que o Santri volta a responder de forma estável.
- O comando de abertura do resultado é enviado uma única vez.

## 2.2.3 — Correção do Estoque Disponível

- A exportação volta a abrir `Valor do estoque` na versão atualizada do Santri.
- `Lista de contagem` removida do caminho utilizado pela automação.

## 2.2.2 — Compatibilidade com o Santri atualizado

- Cadastro de Produtos, Transferências e Estoque Disponível adaptados ao menu atualizado do Santri.
- Compatibilidade mantida com a versão anterior do menu.
- Mensagem objetiva quando um relatório não puder ser localizado.

## 2.2.1 — Correção dos atualizadores

- Execução segura dos atualizadores corporativos armazenados em rede.
- Contexto das pastas de Excel e Access preservado sem modificar a política do Windows.
- Pausas externas removidas do fluxo automático e validação final mantida.

## 2.2.0 — Observabilidade operacional

- Indicadores reais de duração e resultado por etapa.
- Painel de falhas recorrentes agrupadas pela causa registrada.
- Evidências recentes de arquivos com tamanho e SHA-256.
- Central dedicada exclusivamente a notificações, com filtros e direcionamento contextual.
- Configurações administrativas divididas em seis áreas funcionais.
- Monitoramento, diagnósticos, recuperação e versões realocados sem alterar a operação existente.
- Categorias administrativas apresentadas como controles clicáveis, com estados de foco, passagem e seleção.
- Tema claro harmonizado com superfícies cinza SH e contraste corporativo mais suave.

## 2.1.0 — Estabilização operacional

- Validações de execução centralizadas antes do controle do Santri.
- Parâmetros temporários isolados sem alteração do catálogo persistido.
- Compatibilidade integral com os executores Windows homologados.

## 2.0.1 — Correção visual

- Rótulos completos para todos os cinco níveis de prioridade do agendamento.
- Calendário próprio para dias de exceção, integrado aos temas do aplicativo, com inclusão, remoção e datas em DD/MM/AAAA.
- Aba Início permanente, seletores temáticos e limpeza auditada dos itens finalizados da fila.
- Correção da remoção assíncrona, paleta corporativa mais sóbria e central de versões sem cabeçalho redundante.

## 2.0.0 — Plataforma de automações

- Central v2.0 para simular, homologar e enfileirar exportações.
- Registro modular dos três executores Windows existentes.
- Fila persistente com pausa, retomada e cancelamento seguro.
- Configurações versionadas e verificadas por SHA-256.
- Evidências de arquivos gerados vinculadas à execução.

## 1.7.0 — Homologação e atualização

- Ambientes de produção e homologação isolados.
- Canais estável e de testes.
- Consulta segura de releases no repositório oficial.
- Backup obrigatório antes de preparar atualização.
- Verificação SHA-256 do executável baixado.
- Plano de reversão para release anterior.
- Notas das versões dentro do aplicativo.
- Instalador corporativo preparado para assinatura futura.

## 1.6.0 — Agendamentos profissionais

- Calendário consolidado, fila priorizada, exceções e previsões.
- Retentativas configuráveis e retomada por checkpoint.

## 1.5.0 — Monitoramento operacional

- Indicadores reais, alertas, diagnóstico preventivo e retenção.
