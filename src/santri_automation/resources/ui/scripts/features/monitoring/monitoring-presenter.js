export class MonitoringPresenter {
  constructor(htmlEscaper) {
    this.html = htmlEscaper;
  }

  render(value = {}) {
    const overview = value.overview || {};
    const runtime = value.runtime || {};
    const companies = Object.entries(value.companies || {});
    const alerts = value.alerts || [];
    const observability = value.observability || {};
    return `
      <section class="monitoring-command" aria-label="Monitoramento operacional">
        <div class="monitoring-status-row">
          <div>
            <span class="monitoring-eyebrow">Visão operacional · últimos 30 dias</span>
            <h3>Saúde das automações</h3>
          </div>
          <span class="monitoring-state ${this.html.escape(value.status || 'attention')}">${this.status(value.status)}</span>
        </div>
        <div class="monitoring-kpis">
          ${this.kpi('Execuções', overview.executions_30d || 0, 'Fluxos finalizados')}
          ${this.kpi('Taxa de sucesso', `${overview.success_rate_30d || 0}%`, 'Resultado auditado')}
          ${this.kpi('Duração média', this.duration(overview.average_duration_seconds), 'Por sessão')}
          ${this.kpi('Alertas ativos', overview.alerts || 0, overview.alerts ? 'Requer acompanhamento' : 'Nenhuma pendência')}
        </div>
        <div class="runtime-strip">
          ${this.runtime('Sessão Windows', runtime.session_unlocked === true, runtime.session_unlocked ? 'Desbloqueada' : 'Indisponível')}
          ${this.runtime('Santri SOL', runtime.santri_open?.sol === true, runtime.santri_open?.sol ? 'Em execução' : 'Fechado · abertura automática', true)}
          ${this.runtime('Santri HORUS', runtime.santri_open?.horus === true, runtime.santri_open?.horus ? 'Em execução' : 'Fechado · abertura automática', true)}
          ${this.runtime('Empresas', overview.companies_ready === overview.companies_total, `${overview.companies_ready || 0}/${overview.companies_total || 0} disponíveis`)}
        </div>
      </section>

      <div class="monitoring-grid">
        <section class="card monitoring-panel">
          <div class="monitoring-panel-head"><div><h3>Evolução das execuções</h3><span>Sucessos e falhas nos últimos 14 dias</span></div></div>
          ${this.trend(value.trend || [])}
        </section>
        <section class="card monitoring-panel">
          <div class="monitoring-panel-head"><div><h3>Alertas operacionais</h3><span>Agendamentos, ambiente e proteção</span></div><span class="monitoring-alert-count">${alerts.length}</span></div>
          <div class="monitoring-alerts">
            ${alerts.length ? alerts.map(item => this.alertItem(item)).join('') : '<div class="monitoring-empty"><strong>Nenhuma pendência ativa</strong><span>O ambiente está pronto para as próximas execuções.</span></div>'}
          </div>
        </section>
      </div>

      <section class="card monitoring-panel company-performance">
        <div class="monitoring-panel-head"><div><h3>Desempenho por empresa e exportação</h3><span>Disponibilidade, volume, sucesso e duração média</span></div></div>
        <div class="company-performance-grid">
          ${companies.map(([key, company]) => this.company(key, company)).join('')}
        </div>
      </section>

      <div class="observability-grid">
        <section class="card monitoring-panel">
          <div class="monitoring-panel-head"><div><h3>Desempenho por etapa</h3><span>Duração, tentativas e resultado dos últimos ${observability.period_days || 30} dias</span></div></div>
          ${this.stepPerformance(observability.step_performance || [])}
        </section>
        <section class="card monitoring-panel">
          <div class="monitoring-panel-head"><div><h3>Falhas recorrentes</h3><span>Agrupadas pela causa registrada</span></div></div>
          ${this.recurringFailures(observability.recurring_failures || [])}
        </section>
      </div>

      <section class="card monitoring-panel recent-artifacts">
        <div class="monitoring-panel-head"><div><h3>Arquivos observados</h3><span>Evidências recentes vinculadas às execuções</span></div></div>
        ${this.recentArtifacts(observability.recent_artifacts || [])}
      </section>
    `;
  }

  stepPerformance(values) {
    if (!values.length) return this.empty('Sem etapas concluídas', 'Os indicadores serão formados a partir das próximas execuções.');
    return `<div class="observability-list">${values.map(item => `<article class="observability-row"><span><strong>${this.html.escape(item.step)}</strong><small>${this.companyLabel(item.company)} · ${this.html.escape(item.workflow_id || 'fluxo')}</small></span><span><b>${item.success_rate || 0}%</b><small>${item.executions || 0} execução(ões)</small></span><span><b>${this.duration(item.average_duration_seconds)}</b><small>${item.retries || 0} nova(s) tentativa(s)</small></span></article>`).join('')}</div>`;
  }

  recurringFailures(values) {
    if (!values.length) return this.empty('Nenhuma falha recorrente', 'Não há causas repetidas no período analisado.');
    return `<div class="observability-list">${values.map(item => `<article class="observability-row failure"><span><strong>${this.html.escape(item.step)}</strong><small>${this.html.escape(item.message)}</small></span><span><b>${item.count || 0}x</b><small>${this.companyLabel(item.company)}</small></span></article>`).join('')}</div>`;
  }

  recentArtifacts(values) {
    if (!values.length) return this.empty('Nenhum arquivo registrado', 'Arquivos validados aparecerão após as próximas exportações.');
    return `<div class="artifact-observability-list">${values.map(item => `<article><span><strong>${this.html.escape(item.name)}</strong><small>${this.companyLabel(item.company)} · ${this.dateTime(item.finished_at)}</small></span><span><b>${this.fileSize(item.size)}</b><small>${item.sha256 ? `SHA-256 · ${this.html.escape(item.sha256.slice(0, 12))}…` : 'Hash não registrado'}</small></span></article>`).join('')}</div>`;
  }

  empty(title, detail) {
    return `<div class="monitoring-empty compact"><strong>${title}</strong><span>${detail}</span></div>`;
  }

  companyLabel(value) {
    return value === 'sol' ? 'SOL' : value === 'horus' ? 'HORUS' : 'Aplicativo';
  }

  fileSize(value) {
    const bytes = Math.max(0, Number(value || 0));
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  }

  dateTime(value) {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? 'Data não registrada' : parsed.toLocaleString('pt-BR', {dateStyle: 'short', timeStyle: 'short'});
  }

  company(key, company) {
    return `<article class="performance-company ${this.html.escape(key)}">
      <div class="performance-company-head"><strong>${key === 'sol' ? 'SOL ATACADISTA' : 'HORUS DISTRIBUIDORA'}</strong><span class="history-status ${company.ready ? 'success' : 'error'}">${company.ready ? 'Disponível' : 'Verificar'}</span></div>
      <div class="performance-company-summary"><span><small>Execuções</small><strong>${company.executions_30d || 0}</strong></span><span><small>Sucesso</small><strong>${company.success_rate_30d || 0}%</strong></span><span><small>Média</small><strong>${this.duration(company.average_duration_seconds)}</strong></span></div>
      <div class="workflow-performance-list">
        ${(company.workflows || []).map(workflow => `<div class="workflow-performance"><span><strong>${this.html.escape(workflow.name)}</strong><small>${workflow.schedule_enabled ? 'Agendamento ativo' : 'Execução manual'}</small></span><span><strong>${workflow.success_rate_30d || 0}%</strong><small>${workflow.executions_30d || 0} execução(ões) · ${this.duration(workflow.average_duration_seconds)}</small></span><span class="history-status ${workflow.last_status === 'success' ? 'success' : workflow.last_status === 'failed' ? 'error' : 'info'}">${this.executionStatus(workflow.last_status)}</span></div>`).join('')}
      </div>
    </article>`;
  }

  trend(values) {
    const maximum = Math.max(1, ...values.map(item => Number(item.success || 0) + Number(item.failed || 0)));
    return `<div class="monitoring-chart" role="img" aria-label="Execuções concluídas por dia">
      ${values.map(item => {
        const success = Math.max(0, Number(item.success || 0));
        const failed = Math.max(0, Number(item.failed || 0));
        const total = success + failed;
        return `<div class="monitoring-chart-column" title="${this.html.escape(item.date)} · ${success} sucesso(s) · ${failed} falha(s)"><div class="monitoring-chart-value">${total || ''}</div><div class="monitoring-chart-bar"><span class="failed" style="height:${failed * 100 / maximum}%"></span><span class="success" style="height:${success * 100 / maximum}%"></span></div><small>${this.day(item.date)}</small></div>`;
      }).join('')}
    </div><div class="monitoring-legend"><span class="success">Sucesso</span><span class="failed">Falha</span></div>`;
  }

  alertItem(item) {
    return `<article class="monitoring-alert ${this.html.escape(item.level)}"><span class="monitoring-alert-icon">${item.level === 'error' ? '!' : '•'}</span><span><strong>${this.html.escape(item.title)}</strong><small>${this.html.escape(item.message)}</small></span></article>`;
  }

  kpi(label, value, detail) {
    return `<article><small>${label}</small><strong>${value}</strong><span>${detail}</span></article>`;
  }

  runtime(label, ready, detail, informational = false) {
    const state = ready ? 'ready' : informational ? 'neutral' : 'error';
    return `<span class="runtime-state ${state}"><i></i><span><small>${label}</small><strong>${detail}</strong></span></span>`;
  }

  duration(seconds) {
    const value = Math.max(0, Number(seconds || 0));
    if (value < 60) return `${Math.round(value)}s`;
    const minutes = Math.floor(value / 60);
    if (minutes < 60) return `${minutes}min ${String(Math.round(value % 60)).padStart(2, '0')}s`;
    return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}min`;
  }

  day(value) {
    const parsed = new Date(`${value}T12:00:00`);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString('pt-BR', {day: '2-digit', month: '2-digit'});
  }

  status(value) {
    return ({healthy: 'Operação normal', attention: 'Requer atenção', critical: 'Intervenção necessária'})[value] || 'Em verificação';
  }

  executionStatus(value) {
    return ({success: 'Sucesso', failed: 'Falha', never: 'Sem execução'})[value] || 'Em andamento';
  }
}
