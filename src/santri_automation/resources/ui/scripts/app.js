import { AppearanceService } from './core/appearance-service.js';
import { BridgeClient } from './core/bridge-client.js';
import { DashboardSession } from './core/dashboard-session.js';
import { DomRegistry } from './core/dom-registry.js';
import { PageRouter } from './core/page-router.js';
import { HistoryPresenter } from './features/history/history-presenter.js';
import { WorkflowRules } from './features/workflows/workflow-rules.js';
import { HtmlEscaper } from './shared/html-escaper.js';

(() => {
  const icons = {
    building: '<svg viewBox="0 0 24 24"><path d="M3 21h18"></path><path d="M6 21V4h12v17"></path><path d="M9 8h2"></path><path d="M13 8h2"></path><path d="M9 12h2"></path><path d="M13 12h2"></path><path d="M9 16h2"></path><path d="M13 16h2"></path></svg>',
    warehouse: '<svg viewBox="0 0 24 24"><path d="M3 21V8l9-5 9 5v13"></path><path d="M6 12h12"></path><path d="M6 16h12"></path><path d="M9 21v-5"></path><path d="M15 21v-5"></path></svg>',
    plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>',
    play: '<svg viewBox="0 0 24 24"><path d="m8 5 11 7-11 7z"></path></svg>',
    arrow: '<svg viewBox="0 0 24 24"><path d="M5 12h14"></path><path d="m13 6 6 6-6 6"></path></svg>',
    refresh: '<svg viewBox="0 0 24 24"><path d="M20 7V3h-4"></path><path d="m20 3-5 5a7 7 0 0 0-12 4"></path><path d="M4 17v4h4"></path><path d="m4 21 5-5a7 7 0 0 0 12-4"></path></svg>',
    pencil: '<svg viewBox="0 0 24 24"><path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4z"></path></svg>',
    copy: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"></rect><path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3"></path></svg>',
    trash: '<svg viewBox="0 0 24 24"><path d="M3 6h18"></path><path d="M8 6V4h8v2"></path><path d="M19 6l-1 15H6L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path></svg>'
  };

  const fallbackState = {
    settings: {startup_company: 'sol', downloads_folder: '%USERPROFILE%\\\\Downloads', existing_file_policy: 'block', timeout_minutes: 10, keep_activity_log: true, show_success_notification: true, start_with_windows: true, theme: 'light'},
    companies: {
      sol: {name: 'SOL ATACADISTA', environment: 'Santri ADM · CD SIA', login: '1045', unit: '9 · CD - DF', folder: 'S:\\\\00. Procurement\\\\SOL', workflows: []},
      horus: {name: 'HORUS DISTRIBUIDORA', environment: 'Santri ADM · Brasília', login: '753', unit: '1 · BRASILIA', folder: 'S:\\\\00. Procurement\\\\HORUS', workflows: []}
    }
  };

  const session = new DashboardSession(fallbackState);
  const bridge = new BridgeClient(globalThis);
  const dom = new DomRegistry(document);
  const appearance = new AppearanceService(document.documentElement);
  const htmlEscaper = new HtmlEscaper();
  const historyPresenter = new HistoryPresenter(htmlEscaper);
  const workflowRules = new WorkflowRules();
  const router = new PageRouter();
  let toastTimer;
  let confirmationResolver;
  let confirmationReturnFocus;

  const tabsRoot = dom.byId('company-tabs');
  const viewRoot = dom.byId('company-view');
  const editor = dom.byId('editor-company');
  const editorOverlay = dom.byId('editor-overlay');
  const progressCard = dom.byId('progress-company');
  const progressTitle = dom.byId('progress-title');
  const progressDetail = dom.byId('progress-detail');
  const progressValue = dom.byId('progress-value');
  const progressBar = dom.byId('progress-bar');
  const progressLog = dom.byId('progress-log');
  const toast = dom.byId('toast');
  const confirmationOverlay = dom.byId('confirmation-overlay');
  const confirmationModal = dom.byId('confirmation-modal');
  const confirmationEyebrow = dom.byId('confirmation-eyebrow');
  const confirmationTitle = dom.byId('confirmation-title');
  const confirmationMessage = dom.byId('confirmation-message');
  const confirmationContext = dom.byId('confirmation-context');
  const confirmationCancel = dom.byId('confirmation-cancel');
  const confirmationConfirm = dom.byId('confirmation-confirm');
  const startupSplash = dom.byId('startup-splash');
  const startupStatus = dom.byId('startup-status');
  const startupPercent = dom.byId('startup-percent');
  const startupProgress = dom.byId('startup-progress');
  const appScrollRail = dom.byId('app-scroll-rail');
  const appScrollProgress = dom.byId('app-scroll-progress');
  const startupStartedAt = performance.now();

  function wait(milliseconds) {
    return new Promise(resolve => setTimeout(resolve, milliseconds));
  }

  function setStartupStage(message, percentage) {
    startupStatus.textContent = message;
    startupPercent.textContent = String(percentage);
    startupProgress.style.width = `${percentage}%`;
  }

  function applyAppearance(settings = {}) {
    appearance.apply(settings);
  }

  function updateScrollIndicator() {
    const editorIsOpen = editor.classList.contains('open');
    const root = editorIsOpen ? editor : document.documentElement;
    const viewport = editorIsOpen ? editor.clientHeight : globalThis.innerHeight;
    const position = editorIsOpen ? editor.scrollTop : globalThis.scrollY;
    const maximum = Math.max(0, root.scrollHeight - viewport);
    appScrollRail.hidden = maximum < 2 || document.body.classList.contains('starting');
    if (appScrollRail.hidden) return;
    const progress = Math.max(0, Math.min(1, position / maximum));
    appScrollProgress.style.height = `${Math.max(4, progress * 100)}%`;
    appScrollRail.classList.toggle('is-idle', progress === 0);
  }

  async function finishStartup(message) {
    if (session.startupFinished) return;
    session.startupFinished = true;
    setStartupStage(message, 94);
    const remaining = Math.max(0, 2600 - (performance.now() - startupStartedAt));
    await wait(remaining);
    setStartupStage('Tudo pronto. Vamos começar!', 100);
    await wait(420);
    document.body.classList.remove('starting');
    startupSplash.classList.add('is-leaving');
    await wait(680);
    startupSplash.hidden = true;
    updateScrollIndicator();
  }

  function api() {
    return bridge.api;
  }

  async function loadState() {
    if (bridge.isReady()) session.data = await bridge.getState();
    applyAppearance(session.data.settings);
    if (!session.initialized) {
      session.activeCompany = session.data.settings?.startup_company || 'sol';
      session.initialized = true;
    }
    render();
  }

  router
    .register('dashboard', renderCompany)
    .register('history', renderHistory)
    .register('settings', renderSettings)
    .register('reliability', renderReliability)
    .register('about', renderAbout);

  function render() {
    document.getElementById('history-button').classList.toggle('top-nav-active', session.activePage === 'history');
    document.getElementById('reliability-button').classList.toggle('top-nav-active', session.activePage === 'reliability');
    document.getElementById('settings-button').classList.toggle('top-nav-active', session.activePage === 'settings');
    document.getElementById('about-button').classList.toggle('top-nav-active', session.activePage === 'about');
    renderTabs();
    router.render(session.activePage);
    requestAnimationFrame(updateScrollIndicator);
  }
  function renderTabs() {
    tabsRoot.hidden = session.activePage !== 'dashboard';
    if (session.activePage !== 'dashboard') {
      tabsRoot.innerHTML = '';
      return;
    }
    tabsRoot.innerHTML = Object.entries(session.data.companies).map(([key, company]) => {
      const safeKey = escapeHtml(key);
      const logoKey = key === 'sol' ? 'sol' : 'horus';
      return `
      <button class="btn company-tab company-tab-${safeKey} ${key === session.activeCompany ? 'is-selected' : ''}" type="button" role="tab" aria-label="${escapeHtml(company.name)}" aria-selected="${key === session.activeCompany}" data-company="${safeKey}" ${session.busy ? 'disabled' : ''}>
        <span>
          <img class="company-logo" src="./assets/logo-${logoKey}.${logoKey === 'sol' ? 'webp' : 'png'}" alt="${escapeHtml(company.name)}">
          <small>${key === 'sol' ? 'Santri CD SIA · Empresa 9 - CD - DF' : 'Santri Brasília · Empresa 1 - BRASILIA'}</small>
        </span>
      </button>
    `;
    }).join('');
    tabsRoot.querySelectorAll('.company-tab').forEach(button => {
      button.addEventListener('click', async () => {
        if (button.dataset.company === session.activeCompany) return;
        if (!await confirmPendingChanges()) return;
        session.activeCompany = button.dataset.company;
        closeEditor();
        progressCard.classList.remove('visible');
        render();
      });
    });
  }

  function renderCompany() {
    if (session.activePage === 'settings') {
      renderSettings();
      return;
    }
    if (session.activePage === 'history') {
      renderHistory();
      return;
    }
    if (session.activePage === 'about') {
      renderAbout();
      return;
    }
    if (session.activePage === 'reliability') {
      renderReliability();
      return;
    }
    const company = session.data.companies[session.activeCompany];
    const workflows = company.workflows || [];
    const active = workflows.length;
    const implemented = workflows.filter(item => item.implemented).length;
    const last = workflows.find(item => item.last_run && item.last_run !== 'Nunca');
    const scheduled = workflows.find(item => item.enabled && item.implemented && normalizeSchedule(item.schedule).enabled);
    const completedHistory = (session.data.history || []).filter(item => item.company === session.activeCompany && item.category === 'execution' && ['success', 'error'].includes(item.status));
    const successfulHistory = completedHistory.filter(item => item.status === 'success').length;
    const successRate = completedHistory.length ? Math.round(successfulHistory * 100 / completedHistory.length) : null;
    const hasFailure = workflows.some(item => isFailureResult(item.last_result));
    const healthLabel = session.busy ? 'Executando agora' : hasFailure ? 'Requer atenção' : 'Operação normal';
    const healthClass = session.busy ? 'running' : hasFailure ? 'warn' : 'ok';
    viewRoot.innerHTML = `
      <section class="company-view company-view-${escapeHtml(session.activeCompany)}">
        <div class="workspace-head">
          <div class="workspace-title">
            <span>Central de operações</span>
            <h1>${escapeHtml(company.name)}</h1>
            <span class="text-small text-muted">${escapeHtml(company.environment)} · Login ${escapeHtml(company.login)} · Empresa ${escapeHtml(company.unit)} · ambiente isolado</span>
          </div>
          <span class="health-badge ${healthClass}">${healthLabel}</span>
        </div>

        <div class="viz-grid stats">
          <div class="card viz-stat">
            <span class="text-muted">Exportações cadastradas</span>
            <span class="viz-stat-value">${active}</span>
            <span class="text-small">${implemented} pronta(s) · ${Math.max(0, active - implemented)} em configuração</span>
          </div>
          <div class="card viz-stat">
            <span class="text-muted">Última execução</span>
            <span class="viz-stat-value">${escapeHtml(last?.last_run || '—')}</span>
            <span class="status-line ${hasFailure ? 'warn' : ''} text-small">${escapeHtml(last?.last_result || 'Aguardando primeira execução')}</span>
          </div>
          <div class="card viz-stat">
            <span class="text-muted">Próximo lote ${session.activeCompany === 'sol' ? 'SOL' : 'Horus'}</span>
            <span class="viz-stat-value">${escapeHtml(scheduled ? formatSchedule(scheduled.schedule) : 'Desligado')}</span>
            <span class="text-small">${workflows.length} automação(ões) cadastrada(s)</span>
          </div>
          <div class="card viz-stat">
            <span class="text-muted">Taxa de sucesso</span>
            <span class="viz-stat-value">${successRate === null ? '—' : `${successRate}%`}</span>
            <span class="text-small">${completedHistory.length} execução(ões) auditada(s)</span>
          </div>
        </div>

        <div class="section-head">
          <h3>Exportações da ${session.activeCompany === 'sol' ? 'SOL' : 'Horus'}</h3>
          <div class="actions">
            <button class="btn" id="new-report" type="button" title="Cadastrar uma nova exportação nesta empresa" ${session.busy ? 'disabled' : ''}>${icons.plus} Nova exportação</button>
            <button class="btn" id="update-batch" type="button" title="Atualizar somente as bases das exportações marcadas" ${session.busy ? 'disabled' : ''}>${icons.refresh} Atualizar Base</button>
            <button class="btn" id="redirect-batch" type="button" title="Redirecionar os arquivos das exportações marcadas" ${session.busy ? 'disabled' : ''}>${icons.arrow} Redirecionar selecionadas</button>
            <button class="btn btn-primary" id="export-batch" type="button" title="Exportar pelo Santri as exportações marcadas" ${session.busy ? 'disabled' : ''}>${icons.play} Exportar selecionadas</button>
          </div>
        </div>

        <div class="table-responsive">
          <table class="table" id="workflow-table">
            <thead>
              <tr><th class="selection-column"><label class="workflow-selector workflow-selector-all" title="Selecionar ou desmarcar todas as exportações prontas"><input id="select-all-workflows" type="checkbox" ${session.busy ? 'disabled' : ''} aria-label="Selecionar todas as exportações prontas"><span class="workflow-selector-box" aria-hidden="true"></span></label></th><th>Exportação</th><th>Composição</th><th>Agendamento</th><th>Último resultado</th><th class="text-end">Ações</th></tr>
            </thead>
            <tbody>
              ${workflows.length ? workflows.map(workflowRow).join('') : '<tr><td colspan="6" class="empty">Nenhuma exportação cadastrada nesta empresa.</td></tr>'}
            </tbody>
          </table>
        </div>
        <div class="footer-note">
          <span>Uma seleção representa um fluxo completo. As saídas internas não são executadas separadamente.</span>
          <code>${escapeHtml(company.folder)}</code>
        </div>
      </section>
    `;

    document.getElementById('new-report')?.addEventListener('click', () => openEditor());
    document.getElementById('export-batch')?.addEventListener('click', () => runSelected('export'));
    document.getElementById('redirect-batch')?.addEventListener('click', () => runSelected('redirect'));
    document.getElementById('update-batch')?.addEventListener('click', () => runSelected('update'));
    configureWorkflowSelection();
    viewRoot.querySelectorAll('.edit-report').forEach(button => button.addEventListener('click', () => openEditor(button.dataset.id)));
    viewRoot.querySelectorAll('.replicate-report').forEach(button => button.addEventListener('click', () => replicateWorkflow(button.dataset.id, button.dataset.name)));
    viewRoot.querySelectorAll('.delete-report').forEach(button => button.addEventListener('click', () => deleteWorkflow(button.dataset.id, button.dataset.name)));
    viewRoot.querySelectorAll('.run-one').forEach(button => button.addEventListener('click', () => run([button.dataset.id], button.dataset.action)));
  }

  async function deleteWorkflow(id, name) {
    const company = session.data.companies[session.activeCompany];
    const confirmed = await requestConfirmation({
      eyebrow: 'Ação irreversível',
      title: 'Excluir exportação?',
      message: `A exportação “${name}” será removida de ${company.name}. Os arquivos já exportados não serão apagados.`,
      context: `${company.name} · Exportação em construção`,
      confirmLabel: 'Excluir exportação',
      tone: 'danger'
    });
    if (!confirmed) return;
    try {
      if (!api()?.delete_workflow) throw new Error('A ponte com o agente Windows não está disponível.');
      const result = await api().delete_workflow(session.activeCompany, id);
      if (!result.ok) throw new Error(result.error || 'Não foi possível excluir.');
      closeEditor();
      await loadState();
      showToast('Exportação excluída', result.message, false);
    } catch (error) {
      showToast('Não foi possível excluir', String(error.message || error), true);
    }
  }

  async function replicateWorkflow(id, name) {
    const targetCompany = session.activeCompany === 'sol' ? 'horus' : 'sol';
    const sourceName = session.data.companies[session.activeCompany].name;
    const targetName = session.data.companies[targetCompany].name;
    const confirmed = await requestConfirmation({
      eyebrow: 'Replicação entre empresas',
      title: 'Replicar exportação?',
      message: `Será criada uma cópia de “${name}” em ${targetName}. Destino, prefixo e agendamento poderão ser configurados separadamente.`,
      context: `${sourceName} → ${targetName}`,
      confirmLabel: `Replicar para ${targetCompany === 'sol' ? 'SOL' : 'HORUS'}`,
      tone: 'primary'
    });
    if (!confirmed) return;
    try {
      if (!api()?.replicate_workflow) throw new Error('A ponte com o agente Windows não está disponível.');
      const result = await api().replicate_workflow(session.activeCompany, targetCompany, id);
      if (!result.ok) throw new Error(result.error || 'Não foi possível replicar.');
      await loadState();
      showToast('Exportação replicada', result.message, false);
    } catch (error) {
      showToast('Não foi possível replicar', String(error.message || error), true);
    }
  }

  function renderHistory() {
    const entries = (session.data.history || []).filter(entry => {
      const companyMatches = session.historyCompany === 'all' || entry.company === session.historyCompany;
      const categoryMatches = session.historyCategory === 'all' || entry.category === session.historyCategory;
      const statusMatches = session.historyStatus === 'all' || entry.status === session.historyStatus;
      const haystack = `${entry.workflow_name || ''} ${entry.message || ''} ${entry.action || ''}`.toLowerCase();
      return companyMatches && categoryMatches && statusMatches && haystack.includes(session.historySearch.toLowerCase());
    });
    viewRoot.innerHTML = `
      <section class="settings-view">
        <div class="settings-heading">
          <div>
            <h2>Histórico geral</h2>
            <span class="text-small text-muted">Registro persistente das configurações, exclusões e execuções manuais ou agendadas.</span>
          </div>
          <div class="actions">
            <button class="btn" id="export-history" type="button">Exportar CSV</button>
            <button class="btn" id="back-history" type="button">Voltar às exportações</button>
          </div>
        </div>
        <section class="card settings-card">
          <div class="history-filters">
            <label class="form-label">Empresa
              <select id="history-company" class="form-select">
                <option value="all">Todas</option>
                <option value="sol" ${session.historyCompany === 'sol' ? 'selected' : ''}>SOL</option>
                <option value="horus" ${session.historyCompany === 'horus' ? 'selected' : ''}>HORUS</option>
                <option value="system" ${session.historyCompany === 'system' ? 'selected' : ''}>Aplicativo</option>
              </select>
            </label>
            <label class="form-label">Tipo
              <select id="history-category" class="form-select">
                <option value="all">Todos</option>
                <option value="execution" ${session.historyCategory === 'execution' ? 'selected' : ''}>Execuções</option>
                <option value="configuration" ${session.historyCategory === 'configuration' ? 'selected' : ''}>Configurações</option>
              </select>
            </label>
            <label class="form-label">Resultado
              <select id="history-status-filter" class="form-select">
                <option value="all">Todos</option>
                <option value="success" ${session.historyStatus === 'success' ? 'selected' : ''}>Sucesso</option>
                <option value="error" ${session.historyStatus === 'error' ? 'selected' : ''}>Erro</option>
                <option value="started" ${session.historyStatus === 'started' ? 'selected' : ''}>Iniciado</option>
                <option value="blocked" ${session.historyStatus === 'blocked' ? 'selected' : ''}>Bloqueado</option>
              </select>
            </label>
            <label class="form-label">Pesquisar
              <input id="history-search" class="form-control" value="${escapeHtml(session.historySearch)}" placeholder="Exportação ou mensagem">
            </label>
          </div>
          <div class="table-responsive">
            <table class="table history-table">
              <thead><tr><th>Data e hora</th><th>Empresa</th><th>Origem</th><th>Ação</th><th>Exportação</th><th>Resultado</th><th>Descrição</th></tr></thead>
              <tbody>${entries.length ? entries.map(entry => historyPresenter.row(entry)).join('') : '<tr><td colspan="7" class="empty">Nenhuma atividade encontrada para os filtros selecionados.</td></tr>'}</tbody>
            </table>
          </div>
          <div class="footer-note"><span>${entries.length} registro(s) exibido(s) de ${(session.data.history || []).length} armazenado(s).</span><span>Senhas não são registradas.</span></div>
        </section>
      </section>
    `;
    document.getElementById('back-history').addEventListener('click', showDashboard);
    document.getElementById('export-history').addEventListener('click', exportHistory);
    document.getElementById('history-company').addEventListener('change', event => { session.historyCompany = event.target.value; renderHistory(); });
    document.getElementById('history-category').addEventListener('change', event => { session.historyCategory = event.target.value; renderHistory(); });
    document.getElementById('history-status-filter').addEventListener('change', event => { session.historyStatus = event.target.value; renderHistory(); });
    document.getElementById('history-search').addEventListener('change', event => { session.historySearch = event.target.value; renderHistory(); });
  }

  async function exportHistory() {
    try {
      if (!api()?.export_history_csv) throw new Error('A ponte com o agente Windows não está disponível.');
      const result = await api().export_history_csv();
      if (!result.ok) throw new Error(result.error || 'Não foi possível exportar.');
      await loadState();
      showToast('Histórico exportado', `Arquivo salvo em ${result.path}`, false);
    } catch (error) {
      showToast('Não foi possível exportar', String(error.message || error), true);
    }
  }

  function formatHistoryTime(value) {
    return historyPresenter.time(value);
  }

  function isFailureResult(value) {
    return workflowRules.hasFailure(value);
  }

  function renderSettings() {
    const settings = session.data.settings || fallbackState.settings;
    const health = session.data.application?.health || {ready: false, companies: {}};
    const companyHealth = Object.entries(health.companies || {});
    const readyCompanies = companyHealth.filter(([, item]) => item.ready).length;
    const startupCompany = settings.startup_company === 'horus' ? 'HORUS' : 'SOL';
    session.settingsDirty = false;
    viewRoot.innerHTML = `
      <section class="settings-view">
        <header class="settings-heading settings-hero">
          <div class="settings-hero-copy">
            <span class="settings-eyebrow">Administração do aplicativo</span>
            <h2>Configurações gerais</h2>
            <p>Controle o ambiente local, a inicialização e as preferências corporativas do Santri Exportações.</p>
          </div>
          <div class="settings-hero-actions">
            <button class="theme-switch ${settings.theme === 'dark' ? 'is-dark' : ''}" id="setting-theme-toggle" type="button" aria-pressed="${settings.theme === 'dark'}" title="Alternar entre tema claro e escuro">
              <span class="theme-label-light ${settings.theme !== 'dark' ? 'theme-label-active' : ''}">Claro</span>
              <span class="theme-switch-track" aria-hidden="true"><span class="theme-switch-knob"></span></span>
              <span class="theme-label-dark ${settings.theme === 'dark' ? 'theme-label-active' : ''}">Escuro</span>
            </button>
            <button class="btn" id="back-dashboard" type="button">Voltar às exportações</button>
          </div>
        </header>

        <div class="settings-overview" aria-label="Resumo das configurações">
          <article class="settings-overview-card ${health.ready ? 'is-success' : 'is-warning'}">
            <span class="settings-overview-label">Ambiente local</span>
            <strong>${health.ready ? 'Operacional' : 'Requer atenção'}</strong>
            <small>${health.ready ? 'Componentes obrigatórios acessíveis' : 'Verifique o diagnóstico operacional'}</small>
          </article>
          <article class="settings-overview-card">
            <span class="settings-overview-label">Empresas disponíveis</span>
            <strong>${readyCompanies}/${companyHealth.length || 2}</strong>
            <small>SOL Atacadista e HORUS Distribuidora</small>
          </article>
          <article class="settings-overview-card">
            <span class="settings-overview-label">Painel inicial</span>
            <strong>${startupCompany}</strong>
            <small>Empresa exibida ao abrir o aplicativo</small>
          </article>
          <article class="settings-overview-card">
            <span class="settings-overview-label">Aparência</span>
            <strong>${settings.theme === 'dark' ? 'Escura' : 'Clara'}</strong>
            <small>Preferência salva para todo o aplicativo</small>
          </article>
        </div>

        <div class="settings-layout">
          <aside class="card settings-navigation" aria-label="Categorias de configuração">
            <span class="settings-navigation-title">Categorias</span>
            <button class="settings-navigation-item is-active" type="button" data-settings-target="settings-environment"><span>01</span> Ambiente</button>
            <button class="settings-navigation-item" type="button" data-settings-target="settings-startup"><span>02</span> Inicialização</button>
            <button class="settings-navigation-item" type="button" data-settings-target="settings-files"><span>03</span> Arquivos</button>
            <button class="settings-navigation-item" type="button" data-settings-target="settings-notifications"><span>04</span> Registros</button>
            <div class="settings-navigation-note">
              <strong>Escopo global</strong>
              <small>Destino e prefixo permanecem nas configurações de cada exportação.</small>
            </div>
          </aside>

          <div class="settings-content">
            <section class="card settings-card" id="settings-environment">
              <div class="settings-section-head">
                <span class="settings-section-number">01</span>
                <div><h3>Diagnóstico operacional</h3><p>Atalhos, destinos implementados e acesso ao ambiente local.</p></div>
                <span class="health-badge ${health.ready ? 'ok' : 'warn'}">${health.ready ? 'Pronto' : 'Atenção'}</span>
              </div>
              <div class="settings-company-grid">
                ${companyHealth.map(([key, item]) => {
                  const destinations = item.destinations || [];
                  const availableDestinations = destinations.filter(destination => destination.available === true).length;
                  const isSol = key === 'sol';
                  return `<article class="settings-company-status ${isSol ? 'sol' : 'horus'}">
                    <div class="settings-company-brand"><img src="./assets/logo-${isSol ? 'sol.webp' : 'horus.png'}" alt="${isSol ? 'SOL ATACADISTA' : 'HORUS DISTRIBUIDORA'}"><span class="history-status ${item.ready ? 'success' : 'error'}">${item.ready ? 'Disponível' : 'Verificar'}</span></div>
                    <div class="settings-company-metrics"><span><small>Atalho Santri</small><strong>${item.shortcut === true ? 'Localizado' : item.shortcut === null ? 'Tempo excedido' : 'Não encontrado'}</strong></span><span><small>Destinos</small><strong>${availableDestinations}/${destinations.length}</strong></span></div>
                  </article>`;
                }).join('')}
              </div>
            </section>

            <section class="card settings-card" id="settings-startup">
              <div class="settings-section-head"><span class="settings-section-number">02</span><div><h3>Inicialização e execução</h3><p>Comportamento do painel e limites das etapas automatizadas.</p></div></div>
              <div class="settings-grid">
                <label class="form-label">Empresa exibida ao abrir
                  <select id="setting-startup-company" class="form-select">
                    <option value="sol" ${settings.startup_company === 'sol' ? 'selected' : ''}>SOL ATACADISTA</option>
                    <option value="horus" ${settings.startup_company === 'horus' ? 'selected' : ''}>HORUS DISTRIBUIDORA</option>
                  </select>
                </label>
                <label class="form-label">Tempo limite por etapa (minutos)
                  <input id="setting-timeout" class="form-control" type="number" min="1" max="60" value="${escapeHtml(settings.timeout_minutes)}">
                </label>
              </div>
              <div class="setting-toggle">
                <span><strong>Iniciar com o Windows</strong><small class="text-muted">Mantém o agente disponível para executar os horários configurados.</small></span>
                <label class="settings-toggle-control"><input id="setting-start-with-windows" type="checkbox" ${settings.start_with_windows !== false ? 'checked' : ''}><span aria-hidden="true"></span></label>
              </div>
              <div class="settings-information">A automação visual requer o computador ligado e a sessão do Windows aberta e desbloqueada.</div>
            </section>

            <section class="card settings-card" id="settings-files">
              <div class="settings-section-head"><span class="settings-section-number">03</span><div><h3>Arquivos temporários</h3><p>Preparação dos arquivos antes do redirecionamento definitivo.</p></div></div>
              <div class="settings-grid">
                <label class="form-label">Pasta local de exportação
                  <input id="setting-downloads" class="form-control" value="${escapeHtml(settings.downloads_folder)}">
                </label>
                <label class="form-label">Quando o arquivo já existir
                  <select id="setting-file-policy" class="form-select">
                    <option value="block" ${settings.existing_file_policy === 'block' ? 'selected' : ''}>Bloquear e solicitar conferência</option>
                    <option value="replace" ${settings.existing_file_policy === 'replace' ? 'selected' : ''}>Apagar o arquivo anterior e salvar</option>
                  </select>
                </label>
              </div>
            </section>

            <section class="card settings-card" id="settings-notifications">
              <div class="settings-section-head"><span class="settings-section-number">04</span><div><h3>Registros e notificações</h3><p>Visibilidade operacional durante e depois das execuções.</p></div></div>
              <div class="setting-toggle">
                <span><strong>Exibir log detalhado durante a execução</strong><small class="text-muted">O histórico corporativo permanece ativo; esta opção controla somente o painel de progresso.</small></span>
                <label class="settings-toggle-control"><input id="setting-log" type="checkbox" ${settings.keep_activity_log ? 'checked' : ''}><span aria-hidden="true"></span></label>
              </div>
              <div class="setting-toggle">
                <span><strong>Exibir confirmação ao concluir</strong><small class="text-muted">Mostra uma notificação quando todos os arquivos forem finalizados.</small></span>
                <label class="settings-toggle-control"><input id="setting-notification" type="checkbox" ${settings.show_success_notification ? 'checked' : ''}><span aria-hidden="true"></span></label>
              </div>
            </section>
          </div>
        </div>

        <div class="settings-actions">
          <span class="settings-save-state" id="settings-save-state"><span></span>Todas as alterações estão salvas</span>
          <button class="btn" id="cancel-settings" type="button">Cancelar</button>
          <button class="btn btn-primary" id="save-settings" type="button">Salvar configurações</button>
        </div>
      </section>
    `;
    const saveState = document.getElementById('settings-save-state');
    const markSettingsDirty = () => {
      session.settingsDirty = true;
      saveState.classList.add('is-dirty');
      saveState.lastChild.textContent = 'Alterações pendentes';
    };
    const themeToggle = document.getElementById('setting-theme-toggle');
    themeToggle.addEventListener('click', () => {
      const dark = document.documentElement.dataset.theme !== 'dark';
      applyAppearance({theme: dark ? 'dark' : 'light'});
      markSettingsDirty();
      themeToggle.classList.toggle('is-dark', dark);
      themeToggle.setAttribute('aria-pressed', String(dark));
      themeToggle.querySelector('.theme-label-light').classList.toggle('theme-label-active', !dark);
      themeToggle.querySelector('.theme-label-dark').classList.toggle('theme-label-active', dark);
    });
    const cancelSettings = () => {
      applyAppearance(session.data.settings);
      session.settingsDirty = false;
      showDashboard();
    };
    viewRoot.querySelectorAll('.settings-view input, .settings-view select').forEach(control => {
      control.addEventListener('input', markSettingsDirty);
      control.addEventListener('change', markSettingsDirty);
    });
    viewRoot.querySelectorAll('[data-settings-target]').forEach(button => {
      button.addEventListener('click', () => {
        document.getElementById(button.dataset.settingsTarget).scrollIntoView({behavior: 'smooth', block: 'start'});
        viewRoot.querySelectorAll('[data-settings-target]').forEach(item => item.classList.toggle('is-active', item === button));
      });
    });
    document.getElementById('back-dashboard').addEventListener('click', async () => {
      if (await confirmSettingsExit()) showDashboard();
    });
    document.getElementById('cancel-settings').addEventListener('click', cancelSettings);
    document.getElementById('save-settings').addEventListener('click', () => saveSettings(true));
  }

  function renderReliability() {
    const application = session.data.application || {};
    const notifications = application.notifications || [];
    const reports = application.reports || [];
    const backups = application.backups || [];
    const checkpoint = application.pending_checkpoint;
    const diagnostic = session.latestDiagnostic;
    viewRoot.innerHTML = `
      <section class="reliability-view">
        <div class="settings-heading">
          <div>
            <h2>Central de Confiabilidade</h2>
            <span class="text-small text-muted">Diagnósticos, notificações, evidências, relatórios e recuperação operacional da v1.2.</span>
          </div>
          <div class="actions">
            <button class="btn" id="run-diagnostic" type="button">Verificar ambiente</button>
            <button class="btn" id="create-support-package" type="button">Gerar pacote de suporte</button>
            <button class="btn" id="back-reliability" type="button">Voltar</button>
          </div>
        </div>

        ${checkpoint ? `
          <section class="card reliability-card checkpoint-card">
            <div class="section-head">
              <div><h3>Execução disponível para retomada</h3><span class="text-small text-muted">As etapas concluídas ficam registradas e não serão repetidas.</span></div>
              <span class="history-status error">Interrompida</span>
            </div>
            <div class="checkpoint-summary">
              <strong>${escapeHtml(session.data.companies?.[checkpoint.company]?.name || checkpoint.company)} · ${escapeHtml(actionLabel(checkpoint.action))}</strong>
              <span>Etapa interrompida: ${escapeHtml(checkpoint.current_step || 'Preparação')}</span>
              <span>${(checkpoint.completed_steps || []).length} etapa(s) concluída(s) · ID ${escapeHtml(checkpoint.id)}</span>
            </div>
            <div class="actions"><button class="btn btn-primary" id="resume-checkpoint" data-execution-id="${escapeHtml(checkpoint.id)}" type="button">Retomar do último checkpoint</button><button class="btn" id="dismiss-checkpoint" data-execution-id="${escapeHtml(checkpoint.id)}" type="button">Descartar retomada</button></div>
          </section>
        ` : ''}

        <div class="reliability-grid">
          <div class="reliability-stack">
            <section class="card reliability-card">
              <div class="section-head">
                <div><h3>Notificações</h3><span class="text-small text-muted">${application.unread_notifications || 0} não lida(s)</span></div>
                <div class="actions"><button class="btn btn-ghost" id="mark-notifications-read" type="button">Marcar como lidas</button><button class="btn btn-ghost" id="clear-notifications" type="button">Limpar</button></div>
              </div>
              <div class="notification-list">
                ${notifications.length ? notifications.map(item => `
                  <article class="notification-item ${escapeHtml(item.level)} ${item.read ? '' : 'unread'}">
                    <div class="notification-head"><strong>${escapeHtml(item.title)}</strong><span class="history-status ${item.level === 'warning' ? 'blocked' : item.level}">${escapeHtml(notificationLevelLabel(item.level))}</span></div>
                    <p>${escapeHtml(item.message)}</p>
                    <time>${escapeHtml(formatHistoryTime(item.timestamp))}</time>
                  </article>
                `).join('') : '<div class="empty">Nenhuma notificação registrada.</div>'}
              </div>
            </section>

            <section class="card reliability-card">
              <div class="section-head"><div><h3>Backups das configurações</h3><span class="text-small text-muted">Restauração segura do catálogo de exportações.</span></div><button class="btn" id="create-catalog-backup" type="button">Criar backup agora</button></div>
              <div class="backup-list">
                ${backups.length ? backups.slice(0, 8).map(item => `
                  <article class="backup-item">
                    <div class="backup-head"><strong>${item.manual ? 'Backup manual' : 'Backup automático'}</strong><button class="btn btn-ghost restore-backup" type="button" data-name="${escapeHtml(item.name)}">Restaurar</button></div>
                    <time>${escapeHtml(formatHistoryTime(item.modified))} · ${escapeHtml(formatFileSize(item.size))}</time>
                  </article>
                `).join('') : '<div class="empty">Nenhum backup disponível.</div>'}
              </div>
            </section>
          </div>

          <div class="reliability-stack">
            <section class="card reliability-card">
              <div class="section-head"><div><h3>Diagnóstico do ambiente</h3><span class="text-small text-muted">Atalhos, destinos, scripts, permissões e armazenamento.</span></div>${diagnostic ? `<span class="health-badge ${diagnostic.ready ? 'ok' : 'warn'}">${diagnostic.ready ? 'Pronto' : diagnostic.failed + ' atenção'}</span>` : ''}</div>
              <div class="diagnostic-list">
                ${diagnostic ? diagnostic.checks.map(item => `
                  <div class="diagnostic-check"><span><strong>${escapeHtml(item.category)} · ${escapeHtml(item.name)}</strong><small>${escapeHtml(item.detail)}</small></span><span class="history-status ${item.status === 'ok' ? 'success' : item.status === 'warning' ? 'blocked' : 'error'}">${item.status === 'ok' ? 'OK' : item.status === 'warning' ? 'Aviso' : 'Falha'}</span></div>
                `).join('') : '<div class="empty">Clique em “Verificar ambiente” para executar o diagnóstico completo.</div>'}
              </div>
            </section>

            <section class="card reliability-card">
              <div><h3>Relatórios de execução</h3><span class="text-small text-muted">Linha do tempo detalhada, arquivos gerados e evidências de falha.</span></div>
              <div class="report-list">
                ${reports.length ? reports.slice(0, 10).map(report => `
                  <details class="report-item">
                    <summary class="report-head"><strong>${escapeHtml(session.data.companies?.[report.company]?.name || report.company)} · ${escapeHtml(actionLabel(report.action))}</strong><span class="history-status ${report.status === 'success' ? 'success' : 'error'}">${report.status === 'success' ? 'Sucesso' : 'Falha'}</span></summary>
                    <p>ID ${escapeHtml(report.id)} · ${escapeHtml(formatHistoryTime(report.started_at))}</p>
                    ${report.report ? `<p>Relatório: ${escapeHtml(report.report)}</p>` : ''}
                    ${report.evidence ? `<p>Evidência: ${escapeHtml(report.evidence)}</p>` : ''}
                    <div class="timeline">
                      ${(report.timeline || []).slice(-12).map(entry => `<div class="timeline-entry ${escapeHtml(entry.status)}"><span class="timeline-dot"></span><span class="timeline-copy"><strong>${escapeHtml(entry.message)}</strong><small>${escapeHtml(entry.step)} · ${escapeHtml(formatHistoryTime(entry.timestamp))}</small></span></div>`).join('')}
                    </div>
                  </details>
                `).join('') : '<div class="empty">Os próximos fluxos executados gerarão relatórios detalhados aqui.</div>'}
              </div>
            </section>
          </div>
        </div>
      </section>
    `;
    document.getElementById('back-reliability').addEventListener('click', showDashboard);
    document.getElementById('run-diagnostic').addEventListener('click', runDetailedDiagnostic);
    document.getElementById('create-support-package').addEventListener('click', createSupportPackage);
    document.getElementById('mark-notifications-read').addEventListener('click', markNotificationsRead);
    document.getElementById('clear-notifications').addEventListener('click', clearNotifications);
    document.getElementById('create-catalog-backup').addEventListener('click', createCatalogBackup);
    document.getElementById('resume-checkpoint')?.addEventListener('click', event => resumeCheckpoint(event.currentTarget.dataset.executionId));
    document.getElementById('dismiss-checkpoint')?.addEventListener('click', event => dismissCheckpoint(event.currentTarget.dataset.executionId));
    viewRoot.querySelectorAll('.restore-backup').forEach(button => button.addEventListener('click', () => restoreCatalogBackup(button.dataset.name)));
  }

  function notificationLevelLabel(level) {
    return ({success: 'Sucesso', warning: 'Atenção', error: 'Erro', info: 'Informação'})[level] || level;
  }

  function actionLabel(action) {
    return ({all: 'Fluxo completo', export: 'Exportação', redirect: 'Redirecionamento', update: 'Atualização da base'})[action] || action;
  }

  function formatFileSize(value) {
    const bytes = Number(value || 0);
    return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  async function runDetailedDiagnostic() {
    try {
      if (!api()?.run_diagnostics) throw new Error('O agente Windows não disponibilizou o diagnóstico.');
      showToast('Diagnóstico iniciado', 'Verificando todos os componentes do ambiente...', false);
      const result = await api().run_diagnostics();
      if (!result.ok) throw new Error(result.error || 'Não foi possível diagnosticar.');
      session.latestDiagnostic = result.diagnostic;
      await loadState();
      session.activePage = 'reliability';
      render();
      showToast(result.diagnostic.ready ? 'Ambiente pronto' : 'Diagnóstico concluído', result.diagnostic.ready ? 'Todos os componentes obrigatórios estão disponíveis.' : `${result.diagnostic.failed} item(ns) requerem atenção.`, !result.diagnostic.ready);
    } catch (error) {
      showToast('Falha no diagnóstico', String(error.message || error), true);
    }
  }

  async function createSupportPackage() {
    try {
      const result = await api().create_support_package();
      if (!result.ok) throw new Error(result.error || 'Não foi possível gerar o pacote.');
      await loadState();
      session.activePage = 'reliability';
      render();
      showToast('Pacote de suporte criado', result.path, false);
    } catch (error) {
      showToast('Não foi possível gerar o pacote', String(error.message || error), true);
    }
  }

  async function markNotificationsRead() {
    await api().mark_notifications_read();
    await loadState();
    session.activePage = 'reliability';
    render();
  }

  async function clearNotifications() {
    const confirmed = await requestConfirmation({title: 'Limpar notificações?', message: 'Os relatórios e o histórico permanecerão armazenados.', confirmLabel: 'Limpar', tone: 'danger'});
    if (!confirmed) return;
    await api().clear_notifications();
    await loadState();
    session.activePage = 'reliability';
    render();
  }

  async function createCatalogBackup() {
    try {
      const result = await api().create_catalog_backup();
      if (!result.ok) throw new Error(result.error || 'Falha ao criar backup.');
      await loadState();
      session.activePage = 'reliability';
      render();
      showToast('Backup criado', 'As configurações atuais foram protegidas.', false);
    } catch (error) {
      showToast('Falha no backup', String(error.message || error), true);
    }
  }

  async function restoreCatalogBackup(name) {
    const confirmed = await requestConfirmation({title: 'Restaurar configurações?', message: 'As configurações atuais serão protegidas em um novo backup antes da restauração.', context: name, confirmLabel: 'Restaurar', tone: 'danger'});
    if (!confirmed) return;
    try {
      const result = await api().restore_catalog_backup(name);
      if (!result.ok) throw new Error(result.error || 'Falha ao restaurar backup.');
      await loadState();
      session.activePage = 'reliability';
      render();
      showToast('Backup restaurado', 'As configurações foram recuperadas com sucesso.', false);
    } catch (error) {
      showToast('Falha na restauração', String(error.message || error), true);
    }
  }

  async function resumeCheckpoint(executionId) {
    if (session.busy) return;
    session.busy = true;
    progressLog.textContent = '';
    progressTitle.textContent = 'Retomando execução interrompida';
    progressDetail.textContent = 'Carregando o último checkpoint seguro...';
    setProgress(8);
    progressCard.classList.add('visible');
    try {
      const result = await api().resume_execution(executionId);
      if (!result.ok) throw new Error(result.error || 'Não foi possível retomar.');
      setProgress(100);
      progressTitle.textContent = 'Execução retomada e concluída';
      progressDetail.textContent = result.message;
      showToast('Retomada concluída', result.message, false);
    } catch (error) {
      progressTitle.textContent = 'A retomada encontrou um problema';
      progressDetail.textContent = String(error.message || error);
      showToast('Não foi possível retomar', String(error.message || error), true);
    } finally {
      session.busy = false;
      await loadState();
      session.activePage = 'reliability';
      render();
    }
  }

  async function dismissCheckpoint(executionId) {
    const confirmed = await requestConfirmation({title: 'Descartar esta retomada?', message: 'O relatório e as evidências permanecerão disponíveis na Central.', confirmLabel: 'Descartar', tone: 'danger'});
    if (!confirmed) return;
    const result = await api().dismiss_checkpoint(executionId);
    if (!result.ok) {
      showToast('Não foi possível descartar', result.error || 'Checkpoint não encontrado.', true);
      return;
    }
    await loadState();
    session.activePage = 'reliability';
    render();
  }

  function renderAbout() {
    const version = escapeHtml(session.data.application?.version || '1.3.0');
    viewRoot.innerHTML = `
      <section class="about-view">
        <div class="settings-heading">
          <div>
            <h2>Sobre o projeto</h2>
            <span class="text-small text-muted">Identidade, autoria e repositório oficial do Santri Exportações.</span>
          </div>
          <button class="btn" id="back-about" type="button">Voltar às exportações</button>
        </div>

        <section class="card about-hero">
          <div class="about-hero-content">
            <h2>Santri Exportações</h2>
            <p>Aplicação interna do Grupo SH para a SOL ATACADISTA e a HORUS DISTRIBUIDORA.</p>
            <div class="about-version"><span>Versão ${version}</span><span>Aplicação interna Grupo SH</span><span>Windows Desktop</span><span>Licença de uso corporativo</span></div>
          </div>
        </section>

        <section class="card repository-card">
          <div>
            <h3>Repositório oficial</h3>
            <p>A documentação completa, a estrutura do projeto e as orientações de funcionamento estão disponíveis no GitHub.</p>
          </div>
          <button class="btn btn-primary" id="open-repository" type="button">Ver projeto no GitHub</button>
        </section>

        <div class="about-signoff">
          <strong>Idealizado e desenvolvido por Herbert Vieira</strong>
          <span>Projeto original criado para o Grupo SH · SOL ATACADISTA e HORUS DISTRIBUIDORA</span>
        </div>
      </section>
    `;
    document.getElementById('back-about').addEventListener('click', showDashboard);
    document.getElementById('open-repository').addEventListener('click', async () => {
      try {
        const result = await api().open_repository();
        if (!result?.ok) throw new Error('O navegador não confirmou a abertura.');
      } catch (error) {
        showToast('Não foi possível abrir o GitHub', String(error.message || error), true);
      }
    });
  }

  function showDashboard() {
    session.activePage = 'dashboard';
    render();
  }

  async function confirmSettingsExit() {
    if (session.activePage !== 'settings' || !session.settingsDirty) return true;
    const shouldSave = await requestConfirmation({
      eyebrow: 'Alterações não salvas',
      title: 'Deseja salvar as alterações?',
      message: 'As preferências modificadas serão aplicadas nas próximas inicializações do aplicativo.',
      context: 'Configurações gerais · Tema e preferências do aplicativo',
      confirmLabel: 'Salvar alterações',
      cancelLabel: 'Continuar sem salvar'
    });
    if (shouldSave) return saveSettings(false);
    applyAppearance(session.data.settings);
    session.settingsDirty = false;
    return true;
  }

  async function confirmEditorExit() {
    if (!editor.classList.contains('open') || !session.editorDirty) return true;
    const shouldSave = await requestConfirmation({
      eyebrow: 'Alterações não salvas',
      title: 'Deseja salvar a exportação?',
      message: 'As modificações feitas nesta configuração serão perdidas se você continuar sem salvar.',
      context: `${session.data.companies[session.activeCompany].name} · ${document.getElementById('report-name').value || 'Nova exportação'}`,
      confirmLabel: 'Salvar alterações',
      cancelLabel: 'Continuar sem salvar'
    });
    if (shouldSave) return saveWorkflowEditor();
    session.editorDirty = false;
    return true;
  }

  async function confirmPendingChanges() {
    if (!await confirmSettingsExit()) return false;
    return confirmEditorExit();
  }

  async function saveSettings(returnToDashboard = true) {
    const payload = {
      startup_company: document.getElementById('setting-startup-company').value,
      timeout_minutes: Number(document.getElementById('setting-timeout').value),
      downloads_folder: document.getElementById('setting-downloads').value,
      existing_file_policy: document.getElementById('setting-file-policy').value,
      keep_activity_log: document.getElementById('setting-log').checked,
      show_success_notification: document.getElementById('setting-notification').checked,
      start_with_windows: document.getElementById('setting-start-with-windows').checked,
      theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
    };
    try {
      if (!api()?.save_settings) throw new Error('A ponte com o agente Windows não está disponível.');
      session.data.settings = await api().save_settings(payload);
      applyAppearance(session.data.settings);
      session.settingsDirty = false;
      session.activeCompany = session.data.settings.startup_company;
      showToast('Configurações salvas', 'As preferências gerais foram atualizadas.', false);
      if (returnToDashboard) showDashboard();
      return true;
    } catch (error) {
      showToast('Não foi possível salvar', String(error.message || error), true);
      return false;
    }
  }

  function workflowRow(item) {
    const statusClass = ['Validado', 'Concluído', 'Base atualizada'].includes(item.last_result) ? 'ok' : isFailureResult(item.last_result) || !item.implemented ? 'warn' : '';
    return `
      <tr>
        <td class="selection-cell"><label class="workflow-selector" title="${item.implemented ? `Incluir ${escapeHtml(item.name)} nas ações em lote` : 'Disponível quando a exportação estiver pronta'}"><input class="workflow-check" type="checkbox" value="${escapeHtml(item.id)}" ${item.enabled && item.implemented ? 'checked' : ''} ${!item.implemented || session.busy ? 'disabled' : ''} aria-label="Selecionar ${escapeHtml(item.name)}"><span class="workflow-selector-box" aria-hidden="true"></span></label></td>
        <td><span class="report"><strong>${escapeHtml(item.name)}</strong><span class="text-small text-muted">${escapeHtml(item.description)}</span></span></td>
        <td class="composition"><span class="text-small">${item.outputs.length} saída(s) obrigatória(s)</span><span class="composition-list">${item.outputs.map(output => `<span class="chip">${escapeHtml(output)}</span>`).join('')}</span></td>
        <td>${escapeHtml(formatSchedule(item.schedule))}</td>
        <td><span class="run-state ${statusClass}">${escapeHtml(item.last_result)}</span><br><span class="text-small text-muted">${escapeHtml(item.last_run)}</span></td>
        <td><span class="row-actions">
          <button class="btn btn-ghost btn-icon edit-report" type="button" data-id="${escapeHtml(item.id)}" title="Editar exportação" ${session.busy ? 'disabled' : ''}>${icons.pencil}</button>
          ${!item.implemented ? `<button class="btn btn-ghost btn-icon replicate-report" type="button" data-id="${escapeHtml(item.id)}" data-name="${escapeHtml(item.name)}" title="Replicar para ${session.activeCompany === 'sol' ? 'HORUS' : 'SOL'}" ${session.busy ? 'disabled' : ''}>${icons.copy}</button>` : ''}
          ${!item.implemented ? `<button class="btn btn-ghost btn-icon delete-report" type="button" data-id="${escapeHtml(item.id)}" data-name="${escapeHtml(item.name)}" title="Excluir exportação em construção" ${session.busy ? 'disabled' : ''}>${icons.trash}</button>` : ''}
          ${item.implemented ? `
            <button class="btn btn-primary btn-small run-one" type="button" data-action="all" data-id="${escapeHtml(item.id)}" ${session.busy ? 'disabled' : ''}>Executar tudo</button>
            <button class="btn btn-small run-one" type="button" data-action="update" data-id="${escapeHtml(item.id)}" ${session.busy ? 'disabled' : ''}>Atualizar</button>
            <button class="btn btn-small run-one" type="button" data-action="redirect" data-id="${escapeHtml(item.id)}" ${session.busy ? 'disabled' : ''}>Redirecionar</button>
            <button class="btn btn-small run-one" type="button" data-action="export" data-id="${escapeHtml(item.id)}" ${session.busy ? 'disabled' : ''}>Exportar</button>
          ` : '<span class="draft-status">Em construção</span>'}
        </span></td>
      </tr>
    `;
  }

  function configureWorkflowSelection() {
    const selectAll = document.getElementById('select-all-workflows');
    if (!selectAll) return;
    const checkboxes = [...viewRoot.querySelectorAll('.workflow-check:not(:disabled)')];
    const synchronize = () => {
      const selected = checkboxes.filter(input => input.checked).length;
      selectAll.checked = checkboxes.length > 0 && selected === checkboxes.length;
      selectAll.indeterminate = selected > 0 && selected < checkboxes.length;
      selectAll.disabled = session.busy || checkboxes.length === 0;
    };
    selectAll.addEventListener('change', () => {
      checkboxes.forEach(input => { input.checked = selectAll.checked; });
      synchronize();
    });
    checkboxes.forEach(input => input.addEventListener('change', synchronize));
    synchronize();
  }

  function selectedIds() {
    return [...document.querySelectorAll('.workflow-check:checked')].map(input => input.value);
  }

  function runSelected(action) {
    const ids = selectedIds();
    if (!ids.length) {
      showToast('Seleção necessária', 'Selecione ao menos uma exportação pronta.', true);
      return;
    }
    run(ids, action);
  }

  async function run(ids, action) {
    if (session.busy) return;
    session.busy = true;
    session.progressStep = 0;
    progressLog.textContent = '';
    progressLog.hidden = session.data.settings?.keep_activity_log === false;
    const actionTitle = {
      all: 'Executando todas as etapas',
      export: 'Exportando',
      redirect: 'Redirecionando',
      update: 'Atualizando a base'
    }[action] || 'Executando';
    progressTitle.textContent = `${actionTitle} pela ${session.data.companies[session.activeCompany].name}`;
    progressDetail.textContent = 'Preparando a execução...';
    setProgress(5);
    progressCard.classList.add('visible');
    render();
    try {
      if (!api()?.run_workflows) throw new Error('A ponte com o agente Windows não está disponível.');
      const result = await api().run_workflows(session.activeCompany, ids, action);
      if (!result.ok) throw new Error(result.error || 'Não foi possível concluir.');
      setProgress(100);
      progressTitle.textContent = 'Execução concluída';
      progressDetail.textContent = result.message;
      if (session.data.settings?.show_success_notification !== false) {
        showToast('Operação concluída', result.message, false);
      }
      await loadState();
    } catch (error) {
      progressTitle.textContent = 'A execução encontrou um problema';
      progressDetail.textContent = String(error.message || error);
      showToast('Não foi possível concluir', String(error.message || error), true);
    } finally {
      session.busy = false;
      render();
    }
  }

  globalThis.santriUi = {
    onProgress(message) {
      session.progressStep = Math.min(92, session.progressStep + 13);
      setProgress(session.progressStep);
      progressDetail.textContent = message;
      progressLog.textContent += (progressLog.textContent ? '\n' : '') + message;
      progressLog.scrollTop = progressLog.scrollHeight;
    }
  };

  function setProgress(value) {
    const safe = Math.max(0, Math.min(100, value));
    progressValue.textContent = `${safe}%`;
    progressBar.style.width = `${safe}%`;
  }

  function normalizeSchedule(value) {
    if (value && typeof value === 'object' && Array.isArray(value.entries)) {
      return {
        enabled: Boolean(value.enabled),
        entries: value.entries.map(entry => ({weekday: Number(entry.weekday), time: String(entry.time || '')}))
      };
    }
    const text = String(value || '');
    const time = text.match(/\b(?:[01]\d|2[0-3]):[0-5]\d\b/)?.[0];
    if (!time || text.toLowerCase() === 'manual' || text.toLowerCase() === 'desligado') return {enabled: false, entries: []};
    const weekdays = text.toLowerCase().includes('diariamente') ? [0, 1, 2, 3, 4, 5, 6] : [0, 1, 2, 3, 4];
    return {enabled: true, entries: weekdays.map(weekday => ({weekday, time}))};
  }

  function formatSchedule(value) {
    const schedule = normalizeSchedule(value);
    if (!schedule.enabled || !schedule.entries.length) return 'Desligado';
    const labels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
    const times = [...new Set(schedule.entries.map(entry => entry.time))];
    const weekdays = schedule.entries.map(entry => entry.weekday).sort();
    if (times.length === 1 && weekdays.join(',') === '0,1,2,3,4') return `Segunda a sexta · ${times[0]}`;
    if (times.length === 1 && weekdays.join(',') === '0,1,2,3,4,5,6') return `Todos os dias · ${times[0]}`;
    return schedule.entries
      .sort((left, right) => left.weekday - right.weekday)
      .map(entry => `${labels[entry.weekday]} ${entry.time}`)
      .join(' · ');
  }

  function loadScheduleEditor(value) {
    const schedule = normalizeSchedule(value);
    document.getElementById('schedule-mode').value = schedule.enabled ? 'scheduled' : 'off';
    document.querySelectorAll('.schedule-day-check').forEach(checkbox => {
      const weekday = Number(checkbox.dataset.weekday);
      const entry = schedule.entries.find(item => item.weekday === weekday);
      checkbox.checked = Boolean(entry);
      const time = document.querySelector(`.schedule-time[data-weekday="${weekday}"]`);
      time.value = entry?.time || '08:00';
    });
    updateScheduleControls();
  }

  function updateScheduleControls() {
    const enabled = document.getElementById('schedule-mode').value === 'scheduled';
    document.querySelectorAll('.schedule-day-check').forEach(checkbox => {
      checkbox.disabled = !enabled;
      const time = document.querySelector(`.schedule-time[data-weekday="${checkbox.dataset.weekday}"]`);
      time.disabled = !enabled || !checkbox.checked;
    });
  }

  function collectSchedule() {
    const enabled = document.getElementById('schedule-mode').value === 'scheduled';
    const entries = [...document.querySelectorAll('.schedule-day-check:checked')].map(checkbox => ({
      weekday: Number(checkbox.dataset.weekday),
      time: document.querySelector(`.schedule-time[data-weekday="${checkbox.dataset.weekday}"]`).value
    }));
    return {enabled, entries};
  }

  function isTransferWorkflow(id, name) {
    return workflowRules.isTransfer(id, name);
  }

  function isStockWorkflow(id, name) {
    return workflowRules.isStock(id, name);
  }

  function loadStockFilterEditor(item) {
    const container = document.getElementById('stock-filter-editor');
    const visible = isStockWorkflow(item?.id, item?.name);
    container.hidden = !visible;
    if (visible) {
      document.getElementById('stock-asset-consumption-mode').value = item?.include_asset_consumption === false ? 'skip' : 'apply';
    }
  }

  function collectStockFilter() {
    if (document.getElementById('stock-filter-editor').hidden) return null;
    return document.getElementById('stock-asset-consumption-mode').value === 'apply';
  }

  function localDateValue(value) {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, '0');
    const day = String(value.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function automaticTransferDateRange() {
    const today = new Date();
    return {
      start: localDateValue(new Date(today.getFullYear(), today.getMonth() - 1, 1)),
      end: localDateValue(today)
    };
  }

  function formatDateLabel(value) {
    const [year, month, day] = String(value || '').split('-');
    return year && month && day ? `${day}/${month}/${year}` : '—';
  }

  function updateDateRangeControls() {
    const mode = document.getElementById('date-range-mode').value;
    const start = document.getElementById('date-range-start');
    const end = document.getElementById('date-range-end');
    if (mode === 'previous_month_to_today') {
      const automatic = automaticTransferDateRange();
      start.value = automatic.start;
      end.value = automatic.end;
    }
    start.disabled = mode !== 'custom';
    end.disabled = mode !== 'custom';
    const prefix = mode === 'custom' ? 'Período personalizado' : 'Período automático atual';
    document.getElementById('date-range-summary').textContent = `${prefix}: ${formatDateLabel(start.value)} até ${formatDateLabel(end.value)}`;
  }

  function loadDateRangeEditor(item) {
    const container = document.getElementById('transfer-date-editor');
    const visible = isTransferWorkflow(item?.id, item?.name);
    container.hidden = !visible;
    if (!visible) return;
    const configured = item?.date_range || {mode: 'previous_month_to_today'};
    const mode = configured.mode === 'custom' ? 'custom' : 'previous_month_to_today';
    document.getElementById('date-range-mode').value = mode;
    if (mode === 'custom') {
      document.getElementById('date-range-start').value = configured.start || '';
      document.getElementById('date-range-end').value = configured.end || '';
    }
    updateDateRangeControls();
  }

  function collectDateRange() {
    if (document.getElementById('transfer-date-editor').hidden) return null;
    const mode = document.getElementById('date-range-mode').value;
    if (mode !== 'custom') return {mode: 'previous_month_to_today'};
    return {
      mode: 'custom',
      start: document.getElementById('date-range-start').value,
      end: document.getElementById('date-range-end').value
    };
  }

  function openEditor(id = '') {
    const company = session.data.companies[session.activeCompany];
    const item = company.workflows.find(workflow => workflow.id === id);
    document.getElementById('editor-title').textContent = `${item ? 'Editar exportação' : 'Nova exportação'} — ${company.name}`;
    document.getElementById('workflow-id').value = item?.id || '';
    document.getElementById('report-name').value = item?.name || '';
    document.getElementById('report-name').disabled = Boolean(item?.implemented);
    document.getElementById('report-description').value = item?.description || '';
    loadDateRangeEditor(item);
    loadStockFilterEditor(item);
    loadScheduleEditor(item?.schedule);
    document.getElementById('report-path').value = item?.path || '';
    document.getElementById('report-path').disabled = Boolean(item?.implemented);
    document.getElementById('destination-path').value = item?.destination || `${company.folder}\\{relatorio}\\{data}.xlsx`;
    document.getElementById('destination-help').textContent = isStockWorkflow(item?.id, item?.name)
      ? 'Selecione a pasta do mês atual. A planilha será enviada para a subpasta PASTA LEITURA - Arquivo ODS para XLXS.'
      : 'Pasta utilizada para redirecionar os arquivos e atualizar a base.';
    document.getElementById('filename-prefix').value = item?.filename_prefix || (session.activeCompany === 'sol' ? 'Sol' : 'Horus');
    const lockedNote = document.getElementById('locked-note');
    lockedNote.textContent = item?.id === 'cadastro_produtos'
      ? 'Cadastro de Produtos possui composição fixa: Sob encomenda + Completa. As duas saídas sempre serão executadas juntas.'
      : item?.id === 'estoque_disponivel'
      ? 'Estoque Disponível seleciona todas as empresas, gera Dados por empresa - modelo 2 e usa o destino mensal configurado.'
      : 'Esta exportação possui um fluxo Windows validado; caminho e nome permanecem protegidos.';
    lockedNote.classList.toggle('visible', Boolean(item?.implemented));
    selectConfigTab('general');
    updateFilenamePreview();
    editor.classList.add('open');
    editorOverlay.hidden = false;
    document.body.classList.add('editor-open');
    session.editorDirty = false;
    editor.scrollTop = 0;
    requestAnimationFrame(updateScrollIndicator);
  }

  function closeEditor() {
    editor.classList.remove('open');
    editorOverlay.hidden = true;
    document.body.classList.remove('editor-open');
    session.editorDirty = false;
    requestAnimationFrame(updateScrollIndicator);
  }

  document.getElementById('cancel-editor-company').addEventListener('click', async () => {
    if (await confirmEditorExit()) closeEditor();
  });
  editorOverlay.addEventListener('click', async () => {
    if (await confirmEditorExit()) closeEditor();
  });
  editor.querySelectorAll('input, select, textarea').forEach(control => {
    control.addEventListener('input', () => { session.editorDirty = true; });
    control.addEventListener('change', () => { session.editorDirty = true; });
  });
  document.querySelectorAll('.config-tab').forEach(button => {
    button.addEventListener('click', () => selectConfigTab(button.dataset.configTab));
  });
  document.getElementById('filename-prefix').addEventListener('input', updateFilenamePreview);
  document.getElementById('report-name').addEventListener('input', event => {
    if (!document.getElementById('workflow-id').value) {
      loadDateRangeEditor({name: event.target.value});
      loadStockFilterEditor({name: event.target.value});
    }
  });
  document.getElementById('schedule-mode').addEventListener('change', updateScheduleControls);
  document.getElementById('date-range-mode').addEventListener('change', updateDateRangeControls);
  document.getElementById('date-range-start').addEventListener('change', updateDateRangeControls);
  document.getElementById('date-range-end').addEventListener('change', updateDateRangeControls);
  document.querySelectorAll('.schedule-day-check').forEach(checkbox => checkbox.addEventListener('change', updateScheduleControls));

  function selectConfigTab(tab) {
    document.querySelectorAll('.config-tab').forEach(button => button.classList.toggle('is-selected', button.dataset.configTab === tab));
    document.querySelectorAll('.config-panel').forEach(panel => panel.classList.toggle('is-selected', panel.id === `config-${tab}`));
  }

  function updateFilenamePreview() {
    const prefix = document.getElementById('filename-prefix').value.trim() || 'prefixo';
    const workflowId = document.getElementById('workflow-id').value;
    const stockWorkflow = isStockWorkflow(workflowId, document.getElementById('report-name').value);
    const original = workflowId === 'cadastro_produtos'
      ? 'SOBENCOMENDA_relacao_produtos_analitico - data.ods  +  ' + prefix + '_COMPLETO_relacao_produtos_analitico - data.ods'
      : stockWorkflow
      ? 'Valor do estoque analítico - data.ods'
      : 'nome_original_do_santri.xlsx';
    document.getElementById('filename-preview').textContent = `${prefix}_${original}`;
  }

  async function saveWorkflowEditor() {
    const dateRange = collectDateRange();
    const stockFilter = collectStockFilter();
    const payload = {
      id: document.getElementById('workflow-id').value,
      name: document.getElementById('report-name').value,
      description: document.getElementById('report-description').value,
      schedule: collectSchedule(),
      path: document.getElementById('report-path').value,
      destination: document.getElementById('destination-path').value,
      filename_prefix: document.getElementById('filename-prefix').value,
      outputs: ['Arquivo principal'],
      enabled: true
    };
    if (dateRange) payload.date_range = dateRange;
    if (stockFilter !== null) payload.include_asset_consumption = stockFilter;
    if (!payload.name.trim()) {
      showToast('Nome necessário', 'Informe o nome da exportação.', true);
      return false;
    }
    if (payload.schedule.enabled && (!payload.schedule.entries.length || payload.schedule.entries.some(entry => !entry.time))) {
      showToast('Agendamento incompleto', 'Selecione ao menos um dia e informe o horário.', true);
      return false;
    }
    if (dateRange?.mode === 'custom' && (!dateRange.start || !dateRange.end)) {
      showToast('Período incompleto', 'Informe as datas inicial e final de Transferências.', true);
      return false;
    }
    if (dateRange?.mode === 'custom' && dateRange.start > dateRange.end) {
      showToast('Período inválido', 'A data inicial não pode ser posterior à data final.', true);
      return false;
    }
    try {
      if (!api()?.save_workflow) throw new Error('A ponte com o agente Windows não está disponível.');
      await api().save_workflow(session.activeCompany, payload);
      session.editorDirty = false;
      closeEditor();
      await loadState();
      showToast('Exportação salva', 'Descrição, período, arquivos e agendamento foram atualizados.', false);
      return true;
    } catch (error) {
      showToast('Não foi possível salvar', String(error.message || error), true);
      return false;
    }
  }

  document.getElementById('save-editor-company').addEventListener('click', saveWorkflowEditor);

  function showToast(title, message, error) {
    clearTimeout(toastTimer);
    toast.className = `toast${error ? ' error' : ''}`;
    toast.innerHTML = `<strong>${escapeHtml(title)}</strong><span class="text-small text-muted">${escapeHtml(message)}</span>`;
    toast.hidden = false;
    toastTimer = setTimeout(() => { toast.hidden = true; }, 6000);
  }

  function requestConfirmation(options) {
    if (confirmationResolver) closeConfirmation(false);
    confirmationReturnFocus = document.activeElement;
    confirmationEyebrow.textContent = options.eyebrow || 'Confirmação';
    confirmationTitle.textContent = options.title || 'Confirmar ação';
    confirmationMessage.textContent = options.message || '';
    confirmationContext.textContent = options.context || '';
    confirmationContext.hidden = !options.context;
    confirmationConfirm.textContent = options.confirmLabel || 'Confirmar';
    confirmationCancel.textContent = options.cancelLabel || 'Cancelar';
    confirmationConfirm.className = `btn ${options.tone === 'danger' ? 'btn-danger' : 'btn-primary'}`;
    confirmationModal.className = `confirmation-modal company-${session.activeCompany}${options.tone === 'danger' ? ' tone-danger' : ''}`;
    confirmationOverlay.hidden = false;
    confirmationCancel.focus();
    return new Promise(resolve => { confirmationResolver = resolve; });
  }

  function closeConfirmation(result) {
    if (!confirmationResolver) return;
    const resolve = confirmationResolver;
    confirmationResolver = undefined;
    confirmationOverlay.hidden = true;
    if (confirmationReturnFocus instanceof HTMLElement) confirmationReturnFocus.focus();
    confirmationReturnFocus = undefined;
    resolve(result);
  }

  function escapeHtml(value) {
    return htmlEscaper.escape(value);
  }

  confirmationCancel.addEventListener('click', () => closeConfirmation(false));
  confirmationConfirm.addEventListener('click', () => closeConfirmation(true));
  confirmationOverlay.addEventListener('click', event => {
    if (event.target === confirmationOverlay) closeConfirmation(false);
  });
  document.addEventListener('keydown', async event => {
    if (event.key !== 'Escape') return;
    if (!confirmationOverlay.hidden) {
      closeConfirmation(false);
      return;
    }
    if (editor.classList.contains('open') && await confirmEditorExit()) closeEditor();
  });

  document.getElementById('history-button').addEventListener('click', async () => {
    if (!await confirmPendingChanges()) return;
    session.activePage = 'history';
    closeEditor();
    progressCard.classList.remove('visible');
    render();
  });
  document.getElementById('reliability-button').addEventListener('click', async () => {
    if (!await confirmPendingChanges()) return;
    session.activePage = 'reliability';
    closeEditor();
    progressCard.classList.remove('visible');
    if (session.data.application?.unread_notifications) {
      try {
        await api()?.mark_notifications_read?.();
        await loadState();
      } catch (error) {
        showToast('Central de Confiabilidade', 'Não foi possível atualizar as notificações.', true);
      }
    }
    render();
  });
  document.getElementById('settings-button').addEventListener('click', async () => {
    if (session.activePage === 'settings') return;
    if (!await confirmPendingChanges()) return;
    session.activePage = 'settings';
    closeEditor();
    progressCard.classList.remove('visible');
    render();
  });
  document.getElementById('about-button').addEventListener('click', async () => {
    if (!await confirmPendingChanges()) return;
    session.activePage = 'about';
    closeEditor();
    progressCard.classList.remove('visible');
    render();
  });
  globalThis.addEventListener('scroll', updateScrollIndicator, {passive: true});
  globalThis.addEventListener('resize', updateScrollIndicator);
  editor.addEventListener('scroll', updateScrollIndicator, {passive: true});
  new ResizeObserver(() => requestAnimationFrame(updateScrollIndicator)).observe(document.body);

  async function initializeBridge() {
    if (session.bridgeInitializing) return;
    session.bridgeInitializing = true;
    setStartupStage('Iniciando o agente Windows...', 18);
    for (let attempt = 0; attempt < 150; attempt += 1) {
      if (bridge.isReady()) {
        try {
          setStartupStage('Agente Windows conectado', 46);
          await wait(180);
          setStartupStage('Carregando empresas e exportações...', 68);
          await loadState();
          setStartupStage('Validando configurações do ambiente...', 86);
          if (!session.data.application?.health?.ready) {
            setStartupStage('Verificando atalhos, rede, destinos e scripts...', 90);
            await wait(1000);
            continue;
          }
          setStartupStage('SOL e HORUS prontas para operar', 100);
          await finishStartup('Ambiente validado com sucesso');
          session.bridgeInitializing = false;
          return;
        } catch (error) {
          setStartupStage('Aguardando resposta do agente Windows...', 36);
          await wait(100);
          continue;
        }
      }
      if (attempt === 25) setStartupStage('Preparando os módulos de automação...', 28);
      if (attempt === 60) setStartupStage('Finalizando a conexão local...', 34);
      await wait(100);
    }
    session.bridgeInitializing = false;
    setStartupStage('Reiniciando a conexão com o agente Windows...', 34);
    await wait(700);
    globalThis.location.reload();
  }
  window.addEventListener('pywebviewready', initializeBridge);
  initializeBridge();
})();
