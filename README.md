# Santri Exportações

**Projeto idealizado e desenvolvido por Herbert Vieira para o Grupo SH.**

Aplicativo Windows para gerenciar e executar exportações automatizadas do
Santri ERP nos ambientes da **SOL Atacadista** e da **HORUS Distribuidora**.

O aplicativo abre o Santri local, aplica os filtros dos relatórios, gera os
arquivos ODS, redireciona-os às pastas configuradas e atualiza a base.

## Funcionalidades

- Painel separado por empresa.
- Catálogo extensível de exportações.
- Cadastro de Produtos com Base sob encomenda e Base completa.
- Transferências com período automático ou personalizado.
- Estoque Disponível com destino mensal e filtros opcionais.
- Redirecionamento com limpeza controlada das pastas de leitura.
- Execução dos scripts de atualização específicos de cada fluxo.
- Configuração de destino, prefixo e preferências gerais.
- Agendamento empresarial por dia e horário.
- Histórico de auditoria com exportação CSV.
- Backups rotativos e rollback do redirecionamento.
- Diagnóstico de atalhos, rede e destinos.
- Replicação de rascunhos entre SOL e HORUS.
- Central de Confiabilidade com notificações persistentes.
- Diagnóstico completo de atalhos, destinos, scripts e permissões.
- Screenshots automáticos e relatórios HTML/JSON em falhas.
- Retentativas para falhas temporárias e retomada por checkpoint.
- Linha do tempo detalhada e relatório final por execução.
- Backup e restauração das configurações pelo painel.
- Pacote de suporte sanitizado para diagnóstico técnico.

## Requisitos

- Windows 10 ou 11.
- Python 3.11 ou superior para desenvolvimento.
- Microsoft Edge WebView2 Runtime.
- Atalhos `Santri - SOL.lnk` e `Santri - HORUS.lnk` na Área de Trabalho.
- Acesso à unidade de rede `S:`.

## Desenvolvimento

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[build]"
python .\run_local_app.py
```

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Gerar o executável

```powershell
.\scripts\build.ps1
```

O executável será salvo em `dist\Santri Exportações.exe` e o atalho da Área de
Trabalho será atualizado.

## Estrutura

```text
.
├── .github/workflows/       # Validação automática no GitHub
├── docs/                    # Arquitetura
├── scripts/                 # Compilação do aplicativo
├── src/santri_automation/   # Código e recursos
├── tests/                   # Testes automatizados
├── pyproject.toml           # Metadados e dependências
└── run_local_app.py         # Inicializador de desenvolvimento
```

A interface é organizada em HTML semântico, estilos separados por área e módulos JavaScript orientados a objetos. O backend utiliza uma fachada estável, executores por exportação e serviços coesos para capacidades compartilhadas.

## Segurança

O repositório não armazena senhas. O catálogo editável fica fora do Git, em
`%LOCALAPPDATA%\Santri Export`.

Veja [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para os detalhes técnicos e [docs/FILES.md](docs/FILES.md) para o mapa completo dos arquivos.
