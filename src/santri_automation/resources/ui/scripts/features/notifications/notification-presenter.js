export class NotificationPresenter {
  constructor(html) {
    this.html = html;
  }

  render(application, filter, formatTime) {
    const notifications = application.notifications || [];
    const filtered = filter === 'all'
      ? notifications
      : notifications.filter(item => item.level === filter);
    return `<section class="reliability-view">
      <div class="settings-heading"><div><h2>Central de notificações</h2><span class="text-small text-muted">Avisos operacionais do aplicativo em um único lugar.</span></div><div class="actions"><button class="btn btn-ghost" id="mark-notifications-read" type="button">Marcar todas como lidas</button><button class="btn btn-ghost" id="clear-notifications" type="button">Limpar notificações</button></div></div>
      <div class="notification-summary card"><strong>${application.unread_notifications || 0}</strong><span>notificação(ões) não lida(s)</span></div>
      <div class="notification-filters" role="group" aria-label="Filtrar notificações">${this.filters(filter)}</div>
      <section class="card reliability-card"><div class="notification-list">${filtered.length ? filtered.map(item => this.item(item, formatTime)).join('') : '<div class="empty">Nenhuma notificação encontrada para este filtro.</div>'}</div></section>
    </section>`;
  }

  filters(active) {
    return [['all', 'Todas'], ['error', 'Falhas'], ['warning', 'Avisos'], ['success', 'Sucessos']]
      .map(([value, label]) => `<button class="btn ${active === value ? 'btn-primary' : 'btn-ghost'} notification-filter" type="button" data-filter="${value}">${label}</button>`)
      .join('');
  }

  item(item, formatTime) {
    const context = this.context(item);
    return `<article class="notification-item ${this.escape(item.level)} ${item.read ? '' : 'unread'}"><div class="notification-head"><strong>${this.escape(item.title)}</strong><span class="history-status ${item.level === 'warning' ? 'blocked' : item.level}">${this.levelLabel(item.level)}</span></div><p>${this.escape(item.message)}</p><div class="notification-footer"><time>${this.escape(formatTime(item.timestamp))}</time><button class="btn btn-ghost notification-context" type="button" data-page="${context.page}" data-section="${context.section || ''}">${context.label}</button></div></article>`;
  }

  context(item) {
    const text = `${item.title || ''} ${item.message || ''}`.toLowerCase();
    if (/versão|release|atualização/.test(text)) return this.target('settings', 'versions', 'Abrir versões');
    if (/segurança|integridade|assinatura|permiss/.test(text)) return this.target('settings', 'security', 'Abrir segurança');
    if (/ambiente|santri|atalho|destino/.test(text)) return this.target('settings', 'environment', 'Abrir ambiente');
    if (/backup|arquivo|retenção|evidência/.test(text)) return this.target('settings', 'files', 'Abrir arquivos');
    if (/agenda|agend|calendário/.test(text)) return this.target('schedule', '', 'Abrir agenda');
    if (/monitor|checkpoint|execução|fila/.test(text)) return this.target('settings', 'monitoring', 'Abrir monitoramento');
    return this.target('history', '', 'Abrir histórico');
  }

  target(page, section, label) {
    return {page, section, label};
  }

  levelLabel(level) {
    return ({success: 'Sucesso', warning: 'Atenção', error: 'Erro', info: 'Informação'})[level] || level;
  }

  escape(value) {
    return this.html.escape(value);
  }
}
