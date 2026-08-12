export class HistoryPresenter {
  constructor(htmlEscaper) {
    this.html = htmlEscaper;
  }

  row(entry) {
    const details = entry.details && Object.keys(entry.details).length
      ? `<details class="history-details"><summary>Ver detalhes</summary><pre>${this.html.escape(JSON.stringify(entry.details, null, 2))}</pre></details>`
      : '';
    return `<tr>
      <td><span class="text-small">${this.html.escape(this.time(entry.timestamp))}</span></td>
      <td>${this.html.escape(this.company(entry.company))}</td>
      <td>${this.html.escape(entry.source === 'schedule' ? 'Agendado' : entry.source === 'system' ? 'Sistema' : 'Manual')}</td>
      <td>${this.html.escape(this.action(entry.action))}</td>
      <td>${this.html.escape(entry.workflow_name || '—')}</td>
      <td><span class="history-status ${this.html.escape(entry.status)}">${this.html.escape(this.status(entry.status))}</span></td>
      <td><span class="text-small">${this.html.escape(entry.message)}</span>${details}</td>
    </tr>`;
  }

  time(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value || '') : parsed.toLocaleString('pt-BR');
  }

  company(value) {
    return ({sol: 'SOL', horus: 'HORUS', system: 'Aplicativo'})[value] || value;
  }

  action(value) {
    return ({all: 'Executar tudo', export: 'Exportar', redirect: 'Redirecionar', update: 'Atualizar Base', workflow_created: 'Criar exportação', workflow_updated: 'Editar exportação', workflow_deleted: 'Excluir exportação', workflow_replicated: 'Replicar exportação', settings_updated: 'Configurações gerais', application_started: 'Abrir aplicativo', scheduler_error: 'Erro do agendador', history_exported: 'Exportar histórico'})[value] || value;
  }

  status(value) {
    return ({success: 'Sucesso', error: 'Erro', started: 'Iniciado', blocked: 'Bloqueado', info: 'Informação'})[value] || value;
  }
}
