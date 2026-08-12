# Política de segurança

## Versão suportada

A versão 1.4.x recebe correções de segurança. Versões anteriores devem ser atualizadas antes da homologação corporativa.

## Comunicação de vulnerabilidades

Não publique evidências, dados empresariais, caminhos internos ou credenciais em issues públicas. Comunique o responsável técnico Herbert Vieira por um canal corporativo privado, informando versão, impacto, forma de reprodução e evidências sanitizadas.

## Proteções obrigatórias

- O aplicativo utiliza a identidade da sessão do Windows e não armazena senhas do Santri.
- O catálogo, backups, checkpoints, notificações e relatórios possuem verificação de integridade.
- Atualizadores externos são limitados a nomes e destinos autorizados e obedecem à política de execução do Windows.
- Builds geram SBOM e manifesto com SHA-256. A distribuição corporativa deve usar certificado Authenticode da empresa.
- Logs e pacotes de suporte são sanitizados antes de compartilhamento.

## Segredos

Certificados, senhas, tokens, arquivos `.env`, chaves e dados operacionais não devem ser versionados. O repositório contém somente código e configuração não sigilosa.

## Homologação

A liberação deve seguir [SECURITY_HOMOLOGATION.md](docs/SECURITY_HOMOLOGATION.md) e registrar o resultado. Alterações de segurança exigem revisão, testes e novo hash de release.
