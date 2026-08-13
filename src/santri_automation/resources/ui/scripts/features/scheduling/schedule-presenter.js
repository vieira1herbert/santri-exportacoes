export class SchedulePresenter {
  constructor(html) { this.html = html; }

  render(data = {}) {
    const summary = data.summary || {};
    const queue = data.queue || [];
    const calendar = data.calendar || [];
    const days = [...new Set(calendar.map(item => item.date))].slice(0, 14);
    return `
      <section class="schedule-page">
        <div class="page-title-row"><div><span class="page-eyebrow">CENTRAL DE AUTOMAÇÕES · V1.6</span><h2>Agenda profissional</h2><p>Calendário, fila priorizada, exceções, retentativas e previsão dos próximos lotes.</p></div><button class="btn" id="schedule-back" type="button">Voltar às exportações</button></div>
        <div class="schedule-summary">
          ${this.metric('Automações ativas', summary.active || 0, 'Com agenda habilitada')}
          ${this.metric('Próximo lote', this.dateTime(summary.next_run), queue[0]?.workflow_name || 'Nenhum lote previsto')}
          ${this.metric('Exceções', summary.exceptions || 0, 'Datas ignoradas')}
          ${this.metric('Carga estimada', this.duration(summary.estimated_duration_seconds), 'Com base nas execuções anteriores')}
        </div>
        <div class="schedule-layout">
          <section class="card schedule-calendar"><div class="section-head"><div><h3>Próximos 14 dias</h3><span class="text-small text-muted">Visão consolidada de SOL e HORUS</span></div></div>
            <div class="calendar-days">${days.length ? days.map(day => this.day(day, calendar.filter(item => item.date === day))).join('') : '<div class="empty">Nenhum agendamento ativo.</div>'}</div>
          </section>
          <section class="card schedule-queue"><div class="section-head"><div><h3>Fila de execução</h3><span class="text-small text-muted">Ordenada por horário e prioridade</span></div><span class="health-badge ok">${queue.length} lote(s)</span></div>
            <div class="queue-list">${queue.length ? queue.map((item, index) => this.queueItem(item, index)).join('') : '<div class="empty">A fila está vazia.</div>'}</div>
          </section>
        </div>
        <section class="card schedule-dependencies"><div class="section-head"><div><h3>Dependência do fluxo</h3><span class="text-small text-muted">Cada lote respeita a sequência operacional e retoma somente a etapa com falha.</span></div></div>
          <div class="dependency-flow"><span>1 <strong>Exportar</strong></span><i>→</i><span>2 <strong>Redirecionar</strong></span><i>→</i><span>3 <strong>Atualizar base</strong></span></div>
        </section>
      </section>`;
  }

  metric(label, value, note) { return `<article><small>${this.html.escape(label)}</small><strong>${this.html.escape(String(value))}</strong><span>${this.html.escape(note)}</span></article>`; }
  day(date, entries) { const day = new Date(`${date}T12:00:00`); return `<article class="calendar-day"><header><strong>${day.toLocaleDateString('pt-BR',{weekday:'short'})}</strong><span>${day.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})}</span></header>${entries.map(item => `<div class="calendar-event company-${this.html.escape(item.company)}"><time>${this.html.escape(item.time)}</time><span><strong>${this.html.escape(item.workflow_name)}</strong><small>${this.html.escape(item.company_name)}</small></span><b>P${item.priority}</b></div>`).join('')}</article>`; }
  queueItem(item, index) { return `<article class="queue-item company-${this.html.escape(item.company)}"><span class="queue-position">${index + 1}</span><span><strong>${this.html.escape(item.workflow_name)}</strong><small>${this.html.escape(item.company_name)} · prioridade ${item.priority}</small></span><span><strong>${this.dateTime(item.next_run)}</strong><small>término ${this.dateTime(item.estimated_finish)} · ${item.max_attempts} tentativa(s)</small></span><span class="history-status success">Planejado</span></article>`; }
  dateTime(value) { if (!value) return 'Não previsto'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}); }
  duration(seconds) { const value = Number(seconds || 0); if (!value) return '0 min'; return value < 3600 ? `${Math.max(1,Math.round(value/60))} min` : `${Math.floor(value/3600)}h ${Math.round((value%3600)/60)}min`; }
}
