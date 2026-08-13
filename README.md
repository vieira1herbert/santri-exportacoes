# Santri Exportações

> **Objetivo:** reduzir trabalhos manuais por meio de exportações agendadas e padronizadas, disponibilizando as informações com mais rapidez para facilitar a análise dos analistas e apoiar a tomada de decisão.

[![CI](https://github.com/vieira1herbert/santri-exportacoes/actions/workflows/ci.yml/badge.svg)](https://github.com/vieira1herbert/santri-exportacoes/actions/workflows/ci.yml)
[![CodeQL](https://github.com/vieira1herbert/santri-exportacoes/actions/workflows/codeql.yml/badge.svg)](https://github.com/vieira1herbert/santri-exportacoes/actions/workflows/codeql.yml)
![Plataforma](https://img.shields.io/badge/plataforma-Windows-0078D4)
![Versão](https://img.shields.io/badge/versão-2.1.0-314354)
![Uso](https://img.shields.io/badge/uso-interno-00A336)

Aplicação corporativa Windows para gerenciar, executar e auditar exportações automatizadas do Santri ERP nos ambientes da **SOL ATACADISTA** e da **HORUS DISTRIBUIDORA**.

O produto centraliza configurações, agendamentos, execução visual, movimentação segura de arquivos, atualização das bases e evidências operacionais em uma única interface.

> Projeto idealizado e desenvolvido por **Herbert Vieira** para o Grupo SH.

## Visão executiva

O Santri Exportações transforma rotinas repetitivas de extração em fluxos programados e rastreáveis. Os relatórios podem ser executados nos horários definidos, preparados e direcionados automaticamente, reduzindo o tempo operacional e permitindo que os analistas se concentrem na interpretação dos dados, nas exceções e nas decisões do negócio.

Cada automação possui configuração própria por empresa, histórico persistente e etapas independentes para exportar, redirecionar e atualizar a base.

| Capacidade | Resultado |
| --- | --- |
| Gestão centralizada | Exportações, destinos, filtros e horários administrados pela interface |
| Separação empresarial | Configuração e execução independentes para SOL e HORUS |
| Confiabilidade | Checkpoints, retentativas, backups e restauração transacional |
| Rastreabilidade | Histórico, linha do tempo, relatórios e hashes dos arquivos |
| Monitoramento | Saúde por empresa e exportação, alertas, duração e taxa de sucesso |
| Segurança | Integridade criptográfica, ACL do Windows e execução restrita |
| Evolução | Arquitetura modular com executores registráveis por exportação |

## Exportações implementadas

### Cadastro de Produtos

- Geração obrigatória da Base sob encomenda e da Base completa.
- Aplicação dos filtros específicos de cada saída.
- Redirecionamento transacional dos dois arquivos ODS.
- Atualização da base pelo processo corporativo autorizado.

### Transferências

- Período automático ou personalizado.
- Relatório analítico e seleção das unidades autorizadas.
- Redirecionamento e atualização pelo processo corporativo autorizado.

### Estoque Disponível

- Destino mensal configurável por empresa.
- Controle dos filtros Ativo imobilizado e Uso e consumo.
- Exportação Dados por empresa — modelo 2.
- Atualização da base pelo processo corporativo autorizado.

Os atualizadores são recursos corporativos externos e não fazem parte deste repositório.

## Monitoramento e confiabilidade

- Indicadores reais dos últimos 30 dias por empresa e exportação.
- Evolução diária de sucessos e falhas em 14 dias.
- Duração média calculada pelos relatórios persistidos.
- Alertas de agendamento não executado, ambiente indisponível e integridade.
- Detecção da sessão Windows e das instâncias SOL/HORUS do Santri.
- Diagnóstico preventivo obrigatório antes de cada fluxo.
- Resumo técnico copiável e pacote de suporte sanitizado.
- Retenção configurável para histórico, relatórios e evidências.

## Fluxo operacional

```text
Configurar exportação
        ↓
Abrir e validar o Santri
        ↓
Aplicar unidade, período e filtros
        ↓
Exportar e confirmar o arquivo
        ↓
Validar e redirecionar de forma transacional
        ↓
Executar o atualizador autorizado
        ↓
Registrar histórico, evidências e hashes
```

## Arquitetura

```text
Interface HTML/CSS/JavaScript
            ↓
DashboardApi · fachada pywebview
            ↓
Executores · agendamento · confiabilidade
            ↓
Catálogo · segurança · diagnóstico
            ↓
WindowsSantriDriver · arquivos · Santri ERP
```

A interface é composta por HTML semântico, estilos separados por responsabilidade e serviços JavaScript orientados a objetos. O backend Python utiliza fachada, injeção de dependências, executores registráveis e serviços coesos para persistência, segurança, diagnóstico e confiabilidade.

Detalhes técnicos estão em [Arquitetura](docs/ARCHITECTURE.md) e [Mapa de arquivos](docs/FILES.md).

## Segurança corporativa

- Chave de integridade protegida pelo DPAPI do usuário Windows.
- HMAC-SHA256 no catálogo, backups, notificações, checkpoints e relatórios.
- Cadeia autenticada no histórico para detectar alteração retroativa.
- Recuperação pelo último backup íntegro e quarentena da evidência adulterada.
- ACL local restrita ao usuário atual, SYSTEM e Administradores.
- Atualizadores limitados ao nome, tipo e diretório autorizados.
- PowerShell oficial chamado por caminho absoluto e sem bypass da política de execução.
- Sanitização de credenciais em histórico, logs e pacotes de suporte.
- SHA-256 dos arquivos gerados e do executável distribuído.
- SBOM CycloneDX, auditoria de dependências, CodeQL, Dependency Review e Dependabot.
- Suporte a assinatura Authenticode quando houver certificado corporativo.

A aplicação pode operar sem Authenticode enquanto o certificado não estiver disponível. O manifesto mantém esse estado explícito e a integridade da release continua sendo validada pelo SHA-256.

Consulte [Política de segurança](SECURITY.md), [Modelo de ameaças](docs/THREAT_MODEL.md) e [Homologação](docs/SECURITY_HOMOLOGATION.md).

## Requisitos operacionais

- Windows 10 ou Windows 11.
- Microsoft Edge WebView2 Runtime.
- Santri ERP instalado e atalhos das duas empresas disponíveis.
- Acesso às pastas corporativas configuradas.
- Sessão do Windows aberta e desbloqueada durante automações visuais.
- Microsoft Excel e Access quando exigidos pelos atualizadores externos.

O aplicativo usa a autenticação já realizada no Santri e não armazena senhas.

## Ambiente de desenvolvimento

Requer Python 3.11 ou superior e Git.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[build]"
.venv\Scripts\python.exe run_local_app.py
```

## Qualidade e testes

```powershell
python -m pip install -e ".[quality]"
python -m ruff check src tests
python -m black --check src tests
python -m compileall -q src tests build_app.py run_local_app.py
python -m unittest discover -s tests -v
python -m radon cc src/santri_automation -a -s
python -m pip_audit --strict .
```

A suíte cobre regras de negócio, persistência, automação, interface, arquitetura, integridade, auditoria, atualização restrita e cadeia de fornecimento. Os critérios e resultados da auditoria estão documentados em [docs/CODE_QUALITY.md](docs/CODE_QUALITY.md).

## Build Windows

```powershell
python build_app.py
```

O processo gera:

```text
dist/
├── Santri Exportações.exe
├── santri-exportacoes-release.json
└── santri-exportacoes-sbom.cdx.json
```

O manifesto associa versão, commit Git, tamanho, SHA-256, SBOM e estado da assinatura Authenticode.

Para assinar em um ambiente corporativo protegido:

```powershell
$env:SANTRI_SIGNTOOL = "C:\Caminho\signtool.exe"
$env:SANTRI_CERT_THUMBPRINT = "IMPRESSAO_DIGITAL_DO_CERTIFICADO"
$env:SANTRI_TIMESTAMP_URL = "https://servidor-de-timestamp"
python build_app.py
```

Nenhum certificado ou segredo deve ser armazenado no repositório.

## Dados locais

As configurações operacionais ficam fora do Git:

```text
%LOCALAPPDATA%\Santri Export
```

Esse diretório armazena catálogo, chave protegida, backups, histórico, notificações, checkpoints, relatórios e evidências. Arquivos de build e dados locais são ignorados pelo versionamento.

## Estrutura do repositório

```text
.
├── .github/                  Automação de qualidade e segurança
├── docs/                     Arquitetura, arquivos e homologação
├── src/santri_automation/    Aplicação e recursos visuais
├── tests/                    Testes funcionais, arquiteturais e de segurança
├── build_app.py              Build, SBOM, manifesto e assinatura opcional
├── run_local_app.py          Inicializador de desenvolvimento
├── pyproject.toml            Pacote e dependências
├── SECURITY.md               Política de segurança
└── CHANGELOG.md              Evolução do produto
```

## Documentação

| Documento | Finalidade |
| --- | --- |
| [CHANGELOG.md](CHANGELOG.md) | Histórico funcional e técnico das versões |
| [SECURITY.md](SECURITY.md) | Política de segurança e comunicação de vulnerabilidades |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Camadas, dependências e decisões de engenharia |
| [docs/FILES.md](docs/FILES.md) | Responsabilidade de cada arquivo do projeto |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | Ativos, fronteiras, ameaças e riscos residuais |
| [docs/SECURITY_HOMOLOGATION.md](docs/SECURITY_HOMOLOGATION.md) | Evidências exigidas para liberar uma versão |
| [docs/CODE_QUALITY.md](docs/CODE_QUALITY.md) | Linha de base, métricas e riscos de qualidade |

## Autoria e uso

Projeto original idealizado e desenvolvido por **Herbert Vieira** para uso interno do Grupo SH, atendendo **SOL ATACADISTA** e **HORUS DISTRIBUIDORA**.

O código, as configurações e a documentação devem ser utilizados conforme as políticas internas da organização.
