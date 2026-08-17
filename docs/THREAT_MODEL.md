# Modelo de ameaças

## Escopo

O Santri Exportações é uma aplicação Windows interna que controla o Santri ERP, movimenta planilhas e inicia atualizadores mantidos nas pastas corporativas da SOL e da HORUS.

## Ativos protegidos

- integridade das configurações e agendamentos;
- rastreabilidade das ações executadas;
- arquivos exportados e bases de destino;
- sessão autenticada do Santri;
- scripts corporativos de atualização;
- executável distribuído e dependências utilizadas.

## Fronteiras de confiança

| Fronteira | Confiança | Controle |
| --- | --- | --- |
| Sessão do Windows | Identidade corporativa autenticada | DPAPI e privilégio padrão |
| Santri ERP | Aplicativo externo autenticado pelo operador | Automação restrita às janelas esperadas |
| Catálogo local | Dado persistente potencialmente alterável | ACL restrita, HMAC-SHA256, gravação atômica e quarentena |
| Pastas corporativas | Recurso externo administrado pela empresa | Validação de raiz, nome e tipo de arquivo |
| Atualizadores externos | Código fora do repositório | Allowlist, limite de tamanho, bloqueio de links e sessão não interativa sem mudança de política |
| GitHub e build | Cadeia de fornecimento | Dependências fixadas, auditoria, CodeQL, SBOM e hashes |

## Ameaças e mitigações

| Ameaça | Mitigação v1.4 |
| --- | --- |
| Alteração silenciosa do catálogo | Assinatura HMAC com chave protegida por DPAPI e preservação da evidência em quarentena |
| Alteração retroativa do histórico | Cadeia de eventos autenticada e validada na leitura |
| Substituição de um script por caminho malicioso | Caminho resolvido dentro da raiz, nome exato, arquivo regular e bloqueio de links/reparse points |
| Alteração da política de execução | Ausência de `ExecutionPolicy Bypass`, chamada do PowerShell oficial e nenhuma mudança nos escopos de máquina ou usuário |
| Vazamento em log de suporte | Sanitização de credenciais antes da inclusão no ZIP |
| Troca de artefato distribuído | Manifesto de release e SHA-256 do executável e SBOM |
| Dependência vulnerável | Versões fixadas, `pip-audit`, Dependabot e Dependency Review |
| Falha introduzida no código | Testes, compilação e CodeQL |

## Riscos residuais

- A automação visual depende de sessão Windows aberta, desbloqueada e com o Santri na interface esperada.
- Scripts e bases em rede continuam sob responsabilidade de acesso e mudança da infraestrutura corporativa.
- A assinatura Authenticode exige certificado corporativo instalado no ambiente de build.
- A aplicação não substitui EDR, controle de acesso do Windows, backup corporativo ou segregação de permissões das pastas de rede.
