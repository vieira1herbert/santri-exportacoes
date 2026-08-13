export class ReleasePresenter {
  constructor(html) { this.html = html; }

  render(release = {}, check = null) {
    const notes = release.release_notes || [];
    const prepared = (release.installed || []).find(item => item.version !== release.current_version);
    return `<section class="release-page">
      <div class="page-title-row"><div><span class="page-eyebrow">DISTRIBUIÇÃO CONTROLADA · V1.7</span><h2>Homologação e atualizações</h2><p>Controle de ambiente, canal, integridade, backup e reversão das releases internas.</p></div><button class="btn" id="release-back" type="button">Voltar às exportações</button></div>
      <div class="release-hero"><div><small>RELEASE INSTALADA</small><strong>v${this.html.escape(release.current_version || '1.7.0')}</strong><span>${release.environment === 'homologation' ? 'Ambiente de homologação' : 'Ambiente de produção'} · canal ${release.channel === 'test' ? 'de testes' : 'estável'}</span></div><span class="release-sh">SH</span><div class="actions"><button class="btn btn-primary" id="check-release" type="button">Verificar atualização</button>${prepared ? `<button class="btn" id="activate-release" data-version="${this.html.escape(prepared.version)}" type="button">Ativar v${this.html.escape(prepared.version)}</button>` : ''}<button class="btn" id="rollback-release" type="button" ${release.rollback_available ? '' : 'disabled'}>Preparar reversão</button></div></div>
      <div class="release-grid">
        <section class="card release-control"><div class="section-head"><div><h3>Política de distribuição</h3><span class="text-small text-muted">Ambientes isolados e canais independentes.</span></div></div>
          <label class="form-label">Ambiente ativo<select id="release-environment" class="form-select"><option value="production" ${release.environment === 'production' ? 'selected' : ''}>Produção</option><option value="homologation" ${release.environment === 'homologation' ? 'selected' : ''}>Homologação</option></select></label>
          <label class="form-label">Canal de atualização<select id="release-channel" class="form-select"><option value="stable" ${release.channel === 'stable' ? 'selected' : ''}>Estável</option><option value="test" ${release.channel === 'test' ? 'selected' : ''}>Testes</option></select></label>
          <label class="setting-switch"><span><strong>Consultar ao iniciar</strong><small>Somente consulta; instalação sempre exige confirmação.</small></span><input id="release-auto-check" type="checkbox" ${release.automatic_check ? 'checked' : ''}></label>
          <button class="btn btn-primary" id="save-release-preferences" type="button">Salvar política</button>
        </section>
        <section class="card release-status"><div class="section-head"><div><h3>Estado da atualização</h3><span class="text-small text-muted">Origem oficial, hash e backup obrigatório.</span></div></div>${this.checkResult(check)}
          <div class="release-safeguards"><span><b>SHA-256</b> verificação obrigatória</span><span><b>Backup</b> antes de baixar</span><span><b>Assinatura</b> ${this.html.escape(release.signature_status || 'preparada')}</span></div>
        </section>
      </div>
      <section class="card release-notes"><div class="section-head"><div><h3>Notas das versões</h3><span class="text-small text-muted">Histórico exibido diretamente no aplicativo.</span></div></div><div class="release-note-list">${notes.map((item,index) => `<details ${index === 0 ? 'open' : ''}><summary>${this.html.escape(item.title)}</summary><ul>${String(item.body || '').split('\n').filter(Boolean).map(line => `<li>${this.html.escape(line)}</li>`).join('')}</ul></details>`).join('')}</div></section>
    </section>`;
  }

  checkResult(check) {
    if (!check) return '<div class="release-empty"><strong>Nenhuma consulta realizada</strong><span>Clique em “Verificar atualização” para consultar o repositório oficial.</span></div>';
    if (!check.ok) return `<div class="release-empty error"><strong>Consulta indisponível</strong><span>${this.html.escape(check.error || 'Falha desconhecida')}</span></div>`;
    if (!check.available) return `<div class="release-empty success"><strong>Aplicativo atualizado</strong><span>A versão ${this.html.escape(check.current_version)} é a mais recente do canal.</span></div>`;
    return `<div class="release-available"><span><small>NOVA RELEASE</small><strong>v${this.html.escape(check.latest_version)}</strong><b>${this.html.escape(check.name || '')}</b></span><p>${this.html.escape(check.notes || 'Notas não informadas.')}</p><button class="btn btn-primary" id="prepare-release" type="button">Fazer backup e preparar</button></div>`;
  }
}
