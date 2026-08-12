# Homologação de segurança da v1.4

## Evidência automatizada

- [ ] Compilação Python concluída.
- [ ] Suíte completa de testes concluída sem falhas.
- [ ] `pip-audit` sem vulnerabilidade bloqueante.
- [ ] CodeQL sem alerta aberto de severidade alta ou crítica.
- [ ] Dependency Review aprovada.
- [ ] SBOM CycloneDX gerada.
- [ ] Manifesto de release confere o SHA-256 do executável.

## Ambiente Windows

- [ ] Catálogo aparece como integridade verificada na tela Configurações.
- [ ] Trilha de auditoria aparece como cadeia íntegra.
- [ ] Processo opera com privilégio padrão.
- [ ] Pasta local informa ACL restrita ao usuário atual, SYSTEM e Administradores.
- [ ] Os três atualizadores são localizados somente nos destinos autorizados.
- [ ] Nenhum comando utiliza bypass da política de execução.
- [ ] Execuções de Cadastro de Produtos, Transferências e Estoque Disponível foram homologadas em SOL e HORUS.

## Distribuição

- [ ] Quando o certificado corporativo estiver disponível, ele está instalado no Windows Certificate Store.
- [ ] Quando aplicável, `SANTRI_SIGNTOOL` e `SANTRI_CERT_THUMBPRINT` estão definidas apenas no ambiente protegido de build.
- [ ] O manifesto registra corretamente o estado Authenticode como verificado ou não configurado.
- [ ] Hash recebido confere com o manifesto publicado.
- [ ] GitHub Push Protection e proteção da branch principal habilitados pelo administrador do repositório.

## Aprovação

Registrar versão, commit, hash SHA-256, data, ambiente, executor dos testes e aprovador responsável. Enquanto o certificado corporativo não estiver disponível, a aplicação pode operar com o hash da release verificado e o manifesto deve identificar explicitamente a distribuição como não assinada.
