export class PlatformPresenter {
  constructor(html) { this.html = html; }

  render(data = {}, companies = {}, simulation = null) {
    const queue = data.queue || {paused: false, jobs: [], summary: {}};
    const lifecycle = data.lifecycle || {};
    const blueprints = new Map((data.blueprints || []).map(item => [item.workflow_id, item]));
    const workflows = Object.entries(companies).flatMap(([companyKey, company]) => (company.workflows || []).map(workflow => ({companyKey, company, workflow, blueprint: blueprints.get(workflow.id)})));
    return `<section class="platform-page">
      <div class="page-title-row"><div><span class="page-eyebrow">PLATAFORMA CORPORATIVA · V2.0</span><h2>Central de automações</h2><p>Homologação, simulação, fila persistente e rastreabilidade dos fluxos.</p></div><button class="btn" id="platform-back" type="button">Voltar às exportações</button></div>
      <div class="platform-hero"><div><small>CATÁLOGO MODULAR</small><strong>Versão ${this.html.escape(String(data.catalog_version || 2))}</strong><span>${blueprints.size} executor(es) registrado(s) sem alterar os cliques homologados.</span></div><div class="platform-lifecycle"><span><b>${lifecycle.production || 0}</b>Produção</span><span><b>${lifecycle.homologation || 0}</b>Homologação</span><span><b>${lifecycle.draft || 0}</b>Construção</span></div></div>
      ${simulation ? this.simulation(simulation) : ''}
      <div class="platform-layout">
        <section class="card platform-workflows"><div class="section-head"><div><h3>Automações registradas</h3><span class="text-small text-muted">Simule antes de colocar um fluxo na fila operacional.</span></div></div><div class="platform-workflow-list">${workflows.map(item => this.workflow(item)).join('')}</div></section>
        <section class="card platform-queue"><div class="section-head"><div><h3>Fila persistente</h3><span class="text-small text-muted">A fila sobrevive à reinicialização do aplicativo.</span></div><button class="btn" id="platform-queue-toggle" type="button">${queue.paused ? 'Retomar fila' : 'Pausar fila'}</button></div>
          <div class="platform-queue-summary"><span><b>${queue.summary?.queued || 0}</b>Aguardando</span><span><b>${queue.summary?.running || 0}</b>Executando</span><span><b>${queue.summary?.failed || 0}</b>Falhas</span></div>
          <div class="platform-job-list">${queue.jobs?.length ? [...queue.jobs].reverse().slice(0, 12).map(job => this.job(job)).join('') : '<div class="empty">Nenhum item na fila.</div>'}</div>
        </section>
      </div>
    </section>`;
  }

  workflow({companyKey, company, workflow, blueprint}) {
    const lifecycle = workflow.lifecycle || (workflow.implemented ? 'production' : 'draft');
    return `<article class="platform-workflow company-${this.html.escape(companyKey)}"><span><strong>${this.html.escape(workflow.name)}</strong><small>${this.html.escape(company.name)} · ${this.lifecycle(lifecycle)}</small></span><span class="platform-stages">${(blueprint?.stages || []).map(stage => `<i>${stage.order} ${this.html.escape(stage.name)}</i>`).join('') || '<i>Executor pendente</i>'}</span><span class="actions"><button class="btn platform-simulate" data-company="${this.html.escape(companyKey)}" data-workflow="${this.html.escape(workflow.id)}" type="button">Simular</button><button class="btn btn-primary platform-enqueue" data-company="${this.html.escape(companyKey)}" data-workflow="${this.html.escape(workflow.id)}" type="button" ${workflow.implemented && workflow.enabled ? '' : 'disabled'}>Adicionar à fila</button></span></article>`;
  }

  simulation(value) {
    return `<section class="card platform-simulation ${value.ready ? 'approved' : 'blocked'}"><div><small>SIMULAÇÃO SEM CLIQUES</small><strong>${this.html.escape(value.workflow_name || 'Validação')}</strong><span>${this.html.escape(value.message || '')}</span></div><div>${(value.checks || []).map(check => `<span class="platform-check ${check.status}"><b>${check.status === 'ok' ? '✓' : '!'}</b>${this.html.escape(check.message)}</span>`).join('')}</div></section>`;
  }

  job(job) {
    return `<article class="platform-job"><span class="history-status ${this.jobClass(job.status)}">${this.jobStatus(job.status)}</span><span><strong>${this.html.escape(job.workflow_id)}</strong><small>${this.html.escape(String(job.company || '').toUpperCase())} · ${this.html.escape(job.action)}</small></span>${['queued','running'].includes(job.status) ? `<button class="btn btn-danger platform-cancel" data-job="${this.html.escape(job.id)}" type="button">Cancelar</button>` : ''}</article>`;
  }

  lifecycle(value) { return value === 'production' ? 'Produção' : value === 'homologation' ? 'Homologação' : 'Construção'; }
  jobStatus(value) { return {queued:'Aguardando',running:'Executando',completed:'Concluído',failed:'Falha',cancelled:'Cancelado'}[value] || value; }
  jobClass(value) { return value === 'completed' ? 'success' : value === 'failed' ? 'error' : value === 'running' ? 'info' : 'warning'; }
}
