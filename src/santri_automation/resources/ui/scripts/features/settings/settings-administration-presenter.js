export class SettingsAdministrationPresenter {
  constructor(html) {
    this.html = html;
  }

  diagnostic(diagnostic) {
    if (!diagnostic) {
      return '<div class="empty">Execute a verificação para obter o diagnóstico detalhado do ambiente.</div>';
    }
    return diagnostic.checks.map(item => `
      <div class="diagnostic-check">
        <span><strong>${this.escape(item.category)} · ${this.escape(item.name)}</strong><small>${this.escape(item.detail)}</small></span>
        <span class="history-status ${this.statusClass(item.status)}">${this.statusLabel(item.status)}</span>
      </div>
    `).join('');
  }

  backups(backups, formatTime, formatSize) {
    const items = backups.length
      ? backups.slice(0, 8).map(item => `
        <article class="backup-item">
          <div class="backup-head"><strong>${item.manual ? 'Backup manual' : 'Backup automático'}</strong><button class="btn btn-ghost restore-backup" type="button" data-name="${this.escape(item.name)}">Restaurar</button></div>
          <time>${this.escape(formatTime(item.modified))} · ${this.escape(formatSize(item.size))}</time>
        </article>
      `).join('')
      : '<div class="empty">Nenhum backup disponível.</div>';
    return `<div class="settings-subsection">
      <div class="section-head"><div><h3>Backups das configurações</h3><span class="text-small text-muted">Restauração segura do catálogo de exportações.</span></div><button class="btn" id="create-catalog-backup" type="button">Criar backup agora</button></div>
      <div class="backup-list">${items}</div>
    </div>`;
  }

  checkpoint(checkpoint, companyName, actionLabel) {
    if (!checkpoint) return '';
    return `<section class="card reliability-card checkpoint-card">
      <div class="section-head"><div><h3>Execução disponível para retomada</h3><span class="text-small text-muted">As etapas concluídas não serão repetidas.</span></div><span class="history-status error">Interrompida</span></div>
      <div class="checkpoint-summary"><strong>${this.escape(companyName)} · ${this.escape(actionLabel)}</strong><span>Etapa interrompida: ${this.escape(checkpoint.current_step || 'Preparação')}</span><span>${(checkpoint.completed_steps || []).length} etapa(s) concluída(s) · ID ${this.escape(checkpoint.id)}</span></div>
      <div class="actions"><button class="btn btn-primary" id="resume-checkpoint" data-execution-id="${this.escape(checkpoint.id)}" type="button">Retomar do último checkpoint</button><button class="btn" id="dismiss-checkpoint" data-execution-id="${this.escape(checkpoint.id)}" type="button">Descartar retomada</button></div>
    </section>`;
  }

  reports(reports, companies, actionLabel, formatTime) {
    const items = reports.length
      ? reports.slice(0, 10).map(report => this.report(report, companies, actionLabel, formatTime)).join('')
      : '<div class="empty">Os próximos fluxos gerarão relatórios detalhados aqui.</div>';
    return `<section class="card reliability-card"><div><h3>Relatórios de execução</h3><span class="text-small text-muted">Linha do tempo, arquivos gerados e evidências de falha.</span></div><div class="report-list">${items}</div></section>`;
  }

  report(report, companies, actionLabel, formatTime) {
    const company = companies?.[report.company]?.name || report.company;
    const timeline = (report.timeline || []).slice(-12).map(entry => `
      <div class="timeline-entry ${this.escape(entry.status)}"><span class="timeline-dot"></span><span class="timeline-copy"><strong>${this.escape(entry.message)}</strong><small>${this.escape(entry.step)} · ${this.escape(formatTime(entry.timestamp))}</small></span></div>
    `).join('');
    return `<details class="report-item"><summary class="report-head"><strong>${this.escape(company)} · ${this.escape(actionLabel(report.action))}</strong><span class="history-status ${report.status === 'success' ? 'success' : 'error'}">${report.status === 'success' ? 'Sucesso' : 'Falha'}</span></summary><p>ID ${this.escape(report.id)} · ${this.escape(formatTime(report.started_at))}</p>${report.report ? `<p>Relatório: ${this.escape(report.report)}</p>` : ''}${report.evidence ? `<p>Evidência: ${this.escape(report.evidence)}</p>` : ''}<div class="timeline">${timeline}</div></details>`;
  }

  statusClass(status) {
    if (status === 'ok') return 'success';
    if (status === 'warning') return 'blocked';
    return 'error';
  }

  statusLabel(status) {
    if (status === 'ok') return 'OK';
    if (status === 'warning') return 'Aviso';
    return 'Falha';
  }

  escape(value) {
    return this.html.escape(value);
  }
}
