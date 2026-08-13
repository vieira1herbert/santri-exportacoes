import { AppearanceService } from './core/appearance-service.js';
import { BridgeClient } from './core/bridge-client.js';
import { DashboardSession } from './core/dashboard-session.js';
import { DomRegistry } from './core/dom-registry.js';
import { PageRouter } from './core/page-router.js';
import { HistoryPresenter } from './features/history/history-presenter.js';
import { MonitoringPresenter } from './features/monitoring/monitoring-presenter.js';
import { NotificationPresenter } from './features/notifications/notification-presenter.js';
import { SchedulePresenter } from './features/scheduling/schedule-presenter.js';
import { ExceptionDateEditor } from './features/scheduling/exception-date-editor.js';
import { ReleasePresenter } from './features/releases/release-presenter.js';
import { SettingsAdministrationPresenter } from './features/settings/settings-administration-presenter.js';
import { PlatformPresenter } from './features/platform/platform-presenter.js';
import { WorkflowRules } from './features/workflows/workflow-rules.js';
import { HtmlEscaper } from './shared/html-escaper.js';
import { CustomSelectService } from './shared/custom-select-service.js';

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
    settings: {startup_company: 'sol', downloads_folder: '%USERPROFILE%\\\\Downloads', existing_file_policy: 'block', timeout_minutes: 10, keep_activity_log: true, show_success_notification: true, start_with_windows: true, theme: 'light', history_retention_days: 365, artifact_retention_days: 90},
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
  const monitoringPresenter = new MonitoringPresenter(htmlEscaper);
  const notificationPresenter = new NotificationPresenter(htmlEscaper);
  const schedulePresenter = new SchedulePresenter(htmlEscaper);
  const releasePresenter = new ReleasePresenter(htmlEscaper);
  const settingsAdministrationPresenter = new SettingsAdministrationPresenter(htmlEscaper);
  const platformPresenter = new PlatformPresenter(htmlEscaper);
  const workflowRules = new WorkflowRules();
  const router = new PageRouter();
  const customSelects = new CustomSelectService(document);
  customSelects.start();
  const exceptionDateEditor = new ExceptionDateEditor({
    trigger: dom.byId('schedule-exception-date'),
    valueLabel: dom.byId('schedule-exception-value'),
    addButton: dom.byId('schedule-exception-add'),
    calendar: dom.byId('schedule-exception-calendar'),
    monthLabel: dom.byId('schedule-exception-month'),
    previousButton: dom.byId('schedule-exception-previous'),
    nextButton: dom.byId('schedule-exception-next'),
    todayButton: dom.byId('schedule-exception-today'),
    clearButton: dom.byId('schedule-exception-clear'),
    grid: dom.byId('schedule-exception-grid'),
    list: dom.byId('schedule-exception-list'),
    emptyState: dom.byId('schedule-exception-empty')
  },
    () => { session.editorDirty = true; }
  );
  let toastTimer;
  let confirmationResolver;
  let confirmationReturnFocus;
  let releaseCheck;
  let platformSimulation;
  let settingsSection = 'general';
  let notificationFilter = 'all';

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
    .register('schedule', renderSchedule)
    .register('platform', renderPlatform)
    .register('about', renderAbout);

  function render() {
    updateTopbarStatus();
    document.getElementById('home-button').classList.toggle('top-nav-active', session.activePage === 'dashboard');
    document.getElementById('history-button').classList.toggle('top-nav-active', session.activePage === 'history');
    document.getElementById('reliability-button').classList.toggle('top-nav-active', session.activePage === 'reliability');
    document.getElementById('schedule-button').classList.toggle('top-nav-active', session.activePage === 'schedule');
    document.getElementById('platform-button').classList.toggle('top-nav-active', session.activePage === 'platform');
    document.getElementById('settings-button').classList.toggle('top-nav-active', session.activePage === 'settings');
    document.getElementById('about-button').classList.toggle('top-nav-active', session.activePage === 'about');
    renderTabs();
    router.render(session.activePage);
    requestAnimationFrame(updateScrollIndicator);
  }

  function updateTopbarStatus() {
    const status = document.getElementById('agent-status');
    const health = session.data.application?.health;
    const ready = health?.ready === true;
    status.textContent = ready ? 'Agente Windows pronto' : 'Ambiente requer atenção';
    status.classList.toggle('warning', !ready);
    const notificationCount = document.getElementById('notification-count');
    const unread = Number(session.data.application?.unread_notifications || 0);
    notificationCount.textContent = String(unread);
    notificationCount.hidden = unread === 0;
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
    const scheduled = workflows.find(item => item.enabled && item.implemented && normalizeSchedule(item.schedule).enabled);
    const completedHistory = (session.data.history || []).filter(item => item.company === session.activeCompany && item.category === 'execution' && ['success', 'error'].includes(item.status));
    const lastExecution = completedHistory[0];
    const successfulHistory = completedHistory.filter(item => item.status === 'success').length;
    const successRate = completedHistory.length ? Math.round(successfulHistory * 100 / completedHistory.length) : null;
    const hasFailure = workflows.some(item => isFailureResult(item.last_result));
    const companyReady = session.data.application?.health?.companies?.[session.activeCompany]?.ready === true;
    const securityReady = session.data.application?.security?.ready === true;
    const operationReady = companyReady && securityReady && !hasFailure;
    const healthLabel = session.busy ? 'Executando agora' : operationReady ? 'Operação normal' : 'Requer atenção';
    const healthClass = session.busy ? 'running' : operationReady ? 'ok' : 'warn';
    const lastExecutionFailed = lastExecution?.status === 'error';
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
            <span class="viz-stat-value">${escapeHtml(lastExecution ? formatHistoryTime(lastExecution.timestamp) : '—')}</span>
            <span class="status-line ${lastExecutionFailed ? 'warn' : ''} text-small">${escapeHtml(lastExecution ? `${actionLabel(lastExecution.action)} · ${lastExecution.status === 'success' ? 'Sucesso' : 'Falha'}` : 'Aguardando primeira execução')}</span>
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

  function bindSettingsAdministration() {
    document.getElementById('run-diagnostic')?.addEventListener('click', runDetailedDiagnostic);
    document.getElementById('copy-operational-summary')?.addEventListener('click', copyOperationalSummary);
    document.getElementById('create-support-package')?.addEventListener('click', createSupportPackage);
    document.getElementById('create-catalog-backup')?.addEventListener('click', createCatalogBackup);
    document.getElementById('resume-checkpoint')?.addEventListener('click', event => resumeCheckpoint(event.currentTarget.dataset.executionId));
    document.getElementById('dismiss-checkpoint')?.addEventListener('click', event => dismissCheckpoint(event.currentTarget.dataset.executionId));
    viewRoot.querySelectorAll('.restore-backup').forEach(button => button.addEventListener('click', () => restoreCatalogBackup(button.dataset.name)));
    document.getElementById('check-release')?.addEventListener('click', checkRelease);
    document.getElementById('save-release-preferences')?.addEventListener('click', saveReleasePreferences);
    document.getElementById('prepare-release')?.addEventListener('click', prepareRelease);
    document.getElementById('rollback-release')?.addEventListener('click', prepareRollback);
    document.getElementById('activate-release')?.addEventListener('click', event => activateRelease(event.currentTarget.dataset.version));
  }

  function renderSettings() {
    const settings = session.data.settings || fallbackState.settings;
    const application = session.data.application || {};
    const health = session.data.application?.health || {ready: false, companies: {}};
    const security = session.data.application?.security || {ready: false, identity: {}};
    const companyHealth = Object.entries(health.companies || {});
    const readyCompanies = companyHealth.filter(([, item]) => item.ready).length;
    const configuredCompanies = Object.keys(session.data.companies || {}).length;
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
            <strong>${readyCompanies}/${configuredCompanies}</strong>
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
          <article class="settings-overview-card ${security.ready ? 'is-success' : 'is-warning'}">
            <span class="settings-overview-label">Proteção corporativa</span>
            <strong>${security.ready ? 'Verificada' : 'Requer atenção'}</strong>
            <small>Integridade, auditoria e execução autorizada</small>
          </article>
        </div>

        <div class="settings-layout">
          <aside class="card settings-navigation" aria-label="Categorias de configuração">
            <span class="settings-navigation-title">Categorias</span>
            <button class="settings-navigation-item ${settingsSection === 'general' ? 'is-active' : ''}" type="button" data-settings-section="general"><span>01</span> Geral</button>
            <button class="settings-navigation-item ${settingsSection === 'environment' ? 'is-active' : ''}" type="button" data-settings-section="environment"><span>02</span> Ambiente</button>
            <button class="settings-navigation-item ${settingsSection === 'monitoring' ? 'is-active' : ''}" type="button" data-settings-section="monitoring"><span>03</span> Monitoramento</button>
            <button class="settings-navigation-item ${settingsSection === 'files' ? 'is-active' : ''}" type="button" data-settings-section="files"><span>04</span> Arquivos e retenção</button>
            <button class="settings-navigation-item ${settingsSection === 'security' ? 'is-active' : ''}" type="button" data-settings-section="security"><span>05</span> Segurança</button>
            <button class="settings-navigation-item ${settingsSection === 'versions' ? 'is-active' : ''}" type="button" data-settings-section="versions"><span>06</span> Versões</button>
            <div class="settings-navigation-note">
              <strong>Escopo global</strong>
              <small>Destino e prefixo permanecem nas configurações de cada exportação.</small>
            </div>
          </aside>

          <div class="settings-content">
            <section class="card settings-card" id="settings-environment" data-settings-panel="environment" ${settingsSection === 'environment' ? '' : 'hidden'}>
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
              <div class="settings-admin-actions">
                <button class="btn" id="run-diagnostic" type="button">Verificar ambiente</button>
                <button class="btn" id="copy-operational-summary" type="button">Copiar resumo técnico</button>
                <button class="btn" id="create-support-package" type="button">Gerar pacote de suporte</button>
              </div>
              <div class="diagnostic-list">
                ${settingsAdministrationPresenter.diagnostic(session.latestDiagnostic)}
              </div>
            </section>

            <section class="card settings-card" id="settings-startup" data-settings-panel="general" ${settingsSection === 'general' ? '' : 'hidden'}>
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

            <section class="card settings-card" id="settings-files" data-settings-panel="files" ${settingsSection === 'files' ? '' : 'hidden'}>
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

            <section class="card settings-card" id="settings-notifications" data-settings-panel="general" ${settingsSection === 'general' ? '' : 'hidden'}>
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

            <section class="card settings-card" id="settings-retention" data-settings-panel="files" ${settingsSection === 'files' ? '' : 'hidden'}>
              <div class="settings-section-head"><span class="settings-section-number">04</span><div><h3>Retenção e recuperação</h3><p>Prazos de conservação, backups e restauração do catálogo.</p></div></div>
              <div class="settings-grid settings-retention-grid">
                <label class="form-label">Retenção do histórico (dias)
                  <input id="setting-history-retention" class="form-control" type="number" min="30" max="730" value="${escapeHtml(settings.history_retention_days || 365)}">
                </label>
                <label class="form-label">Retenção de relatórios e evidências (dias)
                  <input id="setting-artifact-retention" class="form-control" type="number" min="15" max="365" value="${escapeHtml(settings.artifact_retention_days || 90)}">
                </label>
              </div>
              <div class="settings-information">A limpeza preserva a integridade da trilha mantida e remove somente artefatos que excederem os prazos configurados.</div>
              ${settingsAdministrationPresenter.backups(application.backups || [], formatHistoryTime, formatFileSize)}
            </section>

            <section class="settings-admin-panel" id="settings-monitoring" data-settings-panel="monitoring" ${settingsSection === 'monitoring' ? '' : 'hidden'}>
              ${monitoringPresenter.render(application.monitoring || {})}
              ${settingsAdministrationPresenter.checkpoint(application.pending_checkpoint, session.data.companies?.[application.pending_checkpoint?.company]?.name || application.pending_checkpoint?.company, actionLabel(application.pending_checkpoint?.action))}
              ${settingsAdministrationPresenter.reports(application.reports || [], session.data.companies, actionLabel, formatHistoryTime)}
            </section>

            <section class="card settings-card" id="settings-security" data-settings-panel="security" ${settingsSection === 'security' ? '' : 'hidden'}>
              <div class="settings-section-head"><span class="settings-section-number">05</span><div><h3>Segurança corporativa</h3><p>Controles obrigatórios da versão 1.4 para integridade e rastreabilidade.</p></div><span class="health-badge ${security.ready ? 'ok' : 'warn'}">${security.ready ? 'Verificada' : 'Atenção'}</span></div>
              <div class="security-control-grid">
                <article><small>Configurações</small><strong>${security.configuration_integrity === 'verified' ? 'Integridade verificada' : 'Aguardando validação'}</strong><span>HMAC-SHA256 com chave protegida pelo Windows</span></article>
                <article><small>Trilha de auditoria</small><strong>${security.audit_integrity === 'verified' ? 'Cadeia íntegra' : 'Falha detectada'}</strong><span>Eventos encadeados contra alteração retroativa</span></article>
                <article><small>Armazenamento local</small><strong>${security.local_storage === 'restricted_acl' ? 'Acesso restrito' : 'Permissões padrão'}</strong><span>Usuário atual, SYSTEM e Administradores autorizados</span></article>
                <article><small>Atualizadores</small><strong>${security.update_policy === 'restricted_path_and_name' ? 'Execução restrita' : 'Política não verificada'}</strong><span>Caminho e nomes autorizados, sem desvio de política</span></article>
                <article><small>Identidade Windows</small><strong>${escapeHtml(security.identity?.domain ? security.identity.domain + '\\' + security.identity.user : security.identity?.user || 'Não identificada')}</strong><span>${escapeHtml(security.identity?.computer || '')} · ${security.elevated ? 'Processo elevado' : 'Privilégio padrão'}</span></article>
                <article><small>Release instalada</small><strong>${security.release?.mode === 'development' ? 'Ambiente de desenvolvimento' : security.release?.signed ? 'Assinatura verificada' : 'Release sem assinatura'}</strong><span>${security.release?.verified ? 'Hash do executável conferido' : 'Manifesto não conferido'}</span></article>
              </div>
              <div class="settings-information">Estes controles são permanentes e não podem ser desativados pela interface do aplicativo.</div>
            </section>

            <section class="settings-admin-panel" id="settings-versions" data-settings-panel="versions" ${settingsSection === 'versions' ? '' : 'hidden'}>
              ${releasePresenter.render(application.release || {}, releaseCheck, true)}
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
    viewRoot.querySelectorAll('.settings-view [id^="setting-"]').forEach(control => {
      control.addEventListener('input', markSettingsDirty);
      control.addEventListener('change', markSettingsDirty);
    });
    viewRoot.querySelectorAll('[data-settings-section]').forEach(button => {
      button.addEventListener('click', () => {
        settingsSection = button.dataset.settingsSection;
        viewRoot.querySelectorAll('[data-settings-section]').forEach(item => item.classList.toggle('is-active', item === button));
        viewRoot.querySelectorAll('[data-settings-panel]').forEach(panel => { panel.hidden = panel.dataset.settingsPanel !== settingsSection; });
        viewRoot.scrollIntoView({behavior: 'smooth', block: 'start'});
      });
    });
    bindSettingsAdministration();
    document.getElementById('cancel-settings').addEventListener('click', cancelSettings);
    document.getElementById('save-settings').addEventListener('click', () => saveSettings(true));
  }

  function renderReliability() {
    const application = session.data.application || {};
    viewRoot.innerHTML = notificationPresenter.render(application, notificationFilter, formatHistoryTime);
    document.getElementById('mark-notifications-read').addEventListener('click', markNotificationsRead);
    document.getElementById('clear-notifications').addEventListener('click', clearNotifications);
    viewRoot.querySelectorAll('.notification-filter').forEach(button => button.addEventListener('click', () => { notificationFilter = button.dataset.filter; renderReliability(); }));
    viewRoot.querySelectorAll('.notification-context').forEach(button => button.addEventListener('click', () => openNotificationContext(button.dataset.page, button.dataset.section)));
  }

  function openNotificationContext(page, section) {
    if (page === 'settings') settingsSection = section || 'general';
    session.activePage = page;
    render();
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
      session.activePage = 'settings';
      settingsSection = 'environment';
      render();
      showToast(result.diagnostic.ready ? 'Ambiente pronto' : 'Diagnóstico concluído', result.diagnostic.ready ? 'Todos os componentes obrigatórios estão disponíveis.' : `${result.diagnostic.failed} item(ns) requerem atenção.`, !result.diagnostic.ready);
    } catch (error) {
      showToast('Falha no diagnóstico', String(error.message || error), true);
    }
  }

  function renderSchedule() {
    viewRoot.innerHTML = schedulePresenter.render(session.data.application?.scheduling || {});
  }

  function renderPlatform() {
    const platform = session.data.application?.platform || {};
    viewRoot.innerHTML = platformPresenter.render(platform, session.data.companies, platformSimulation);
    document.getElementById('platform-queue-toggle').addEventListener('click', toggleExecutionQueue);
    document.querySelectorAll('.platform-simulate').forEach(button => button.addEventListener('click', simulatePlatformWorkflow));
    document.querySelectorAll('.platform-enqueue').forEach(button => button.addEventListener('click', enqueuePlatformWorkflow));
    document.querySelectorAll('.platform-cancel').forEach(button => button.addEventListener('click', cancelPlatformJob));
    document.querySelectorAll('.platform-remove').forEach(button => button.addEventListener('click', removePlatformJob));
  }

  async function simulatePlatformWorkflow(event) {
    try {
      const {company, workflow} = event.currentTarget.dataset;
      platformSimulation = await api().simulate_workflow(company, workflow, 'all');
      renderPlatform();
      showToast(platformSimulation.ready ? 'Simulação aprovada' : 'Simulação bloqueada', platformSimulation.message, !platformSimulation.ready);
    } catch (error) {
      showToast('Falha na simulação', String(error.message || error), true);
    }
  }

  async function enqueuePlatformWorkflow(event) {
    const {company, workflow} = event.currentTarget.dataset;
    const confirmed = await requestConfirmation({title: 'Adicionar à fila operacional?', message: 'A simulação preventiva será executada antes do enfileiramento. O fluxo completo iniciará quando o agente estiver livre.', confirmLabel: 'Adicionar à fila'});
    if (!confirmed) return;
    try {
      const result = await api().enqueue_workflows(company, [workflow], 'all');
      if (!result.ok) return showToast('Fila bloqueada', result.error, true);
      await loadState();
      session.activePage = 'platform';
      render();
      showToast('Fluxo enfileirado', 'A execução foi adicionada à fila persistente.', false);
    } catch (error) {
      showToast('Falha ao enfileirar', String(error.message || error), true);
    }
  }

  async function toggleExecutionQueue() {
    try {
      const paused = Boolean(session.data.application?.platform?.queue?.paused);
      if (paused) await api().resume_execution_queue();
      else await api().pause_execution_queue();
      await loadState();
      session.activePage = 'platform';
      render();
      showToast(paused ? 'Fila retomada' : 'Fila pausada', paused ? 'Novos itens podem ser processados.' : 'O item atual termina no ponto seguro; novos itens aguardarão.', false);
    } catch (error) {
      showToast('Falha ao alterar fila', String(error.message || error), true);
    }
  }

  async function cancelPlatformJob(event) {
    const jobId = event.currentTarget.dataset.job;
    const confirmed = await requestConfirmation({title: 'Cancelar item da fila?', message: 'Itens aguardando serão cancelados imediatamente. Uma execução ativa será interrompida no próximo ponto seguro entre etapas.', confirmLabel: 'Cancelar item', tone: 'danger'});
    if (!confirmed) return;
    try {
      await api().cancel_queue_item(jobId);
      await loadState();
      session.activePage = 'platform';
      render();
    } catch (error) {
      showToast('Falha ao cancelar', String(error.message || error), true);
    }
  }

  async function removePlatformJob(event) {
    const jobId = event.currentTarget.dataset.job;
    const confirmed = await requestConfirmation({title: 'Remover item da fila?', message: 'O item será retirado da fila persistente. O histórico de auditoria da remoção continuará disponível.', confirmLabel: 'Remover item', tone: 'danger'});
    if (!confirmed) return;
    try {
      await api().remove_queue_item(jobId);
      await loadState();
      session.activePage = 'platform';
      render();
      showToast('Item removido', 'O registro foi retirado da fila persistente.', false);
    } catch (error) {
      showToast('Falha ao remover', String(error.message || error), true);
    }
  }

  async function checkRelease() {
    const button = document.getElementById('check-release');
    try {
      if (!api()?.check_for_updates) throw new Error('O agente Windows não disponibilizou a consulta de atualizações.');
      button.disabled = true;
      button.textContent = 'Consultando...';
      showToast('Consultando versões', 'Acessando o repositório oficial...', false);
      releaseCheck = await api().check_for_updates(document.getElementById('release-channel').value);
      renderSettings();
    } catch (error) {
      releaseCheck = {ok: false, error: String(error.message || error)};
      renderSettings();
      showToast('Consulta indisponível', String(error.message || error), true);
    }
  }

  async function saveReleasePreferences() {
    const environment = document.getElementById('release-environment').value;
    const confirmed = await requestConfirmation({title: 'Salvar política de distribuição?', message: environment === 'homologation' ? 'O catálogo de homologação é isolado da produção e será carregado na próxima inicialização.' : 'O catálogo de produção será carregado na próxima inicialização.', confirmLabel: 'Salvar política'});
    if (!confirmed) return;
    const result = await api().save_release_preferences({environment, channel: document.getElementById('release-channel').value, automatic_check: document.getElementById('release-auto-check').checked});
    await loadState();
    session.activePage = 'settings';
    settingsSection = 'versions';
    render();
    showToast('Política salva', result.restart_required ? 'Reinicie o aplicativo para trocar o ambiente ativo.' : 'Preferências atualizadas.', false);
  }

  async function prepareRelease() {
    if (!releaseCheck?.available) return;
    const confirmed = await requestConfirmation({title: `Preparar versão ${releaseCheck.latest_version}?`, message: 'O catálogo atual será copiado antes do download. O executável só será aceito se corresponder ao SHA-256 do manifesto oficial.', confirmLabel: 'Fazer backup e preparar'});
    if (!confirmed) return;
    const result = await api().prepare_update(releaseCheck);
    if (!result.ok) return showToast('Atualização bloqueada', result.error, true);
    await loadState();
    session.activePage = 'settings';
    settingsSection = 'versions';
    render();
    showToast('Release preparada', `Versão ${result.version} verificada. A ativação exige reinicialização controlada.`, false);
  }

  async function prepareRollback() {
    const confirmed = await requestConfirmation({title: 'Preparar reversão?', message: 'O aplicativo localizará a release anterior verificada e o backup associado. Nenhum arquivo será substituído durante esta etapa.', confirmLabel: 'Preparar reversão', tone: 'danger'});
    if (!confirmed) return;
    const result = await api().rollback_release();
    showToast(result.ok ? 'Reversão disponível' : 'Reversão indisponível', result.ok ? `Versão ${result.version} pronta para ativação após reiniciar.` : result.error, !result.ok);
  }

  async function activateRelease(version) {
    const confirmed = await requestConfirmation({title: `Ativar versão ${version}?`, message: 'O atalho corporativo passará a iniciar esta release verificada. Reinicie o aplicativo para concluir a troca.', confirmLabel: 'Ativar release'});
    if (!confirmed) return;
    const result = await api().activate_release(version);
    showToast(result.ok ? 'Release ativada' : 'Ativação bloqueada', result.ok ? 'Feche e abra o aplicativo pelo atalho para concluir.' : result.error, !result.ok);
  }

  async function copyOperationalSummary() {
    try {
      if (!api()?.copy_operational_summary) throw new Error('O agente Windows não disponibilizou o resumo operacional.');
      const result = await api().copy_operational_summary();
      if (!result.ok) throw new Error(result.error || 'Não foi possível copiar o resumo.');
      showToast('Resumo copiado', 'O diagnóstico operacional está pronto para ser enviado ao suporte.', false);
    } catch (error) {
      showToast('Falha ao copiar', String(error.message || error), true);
    }
  }

  async function createSupportPackage() {
    try {
      const result = await api().create_support_package();
      if (!result.ok) throw new Error(result.error || 'Não foi possível gerar o pacote.');
      await loadState();
      session.activePage = 'settings';
      settingsSection = 'environment';
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
      session.activePage = 'settings';
      settingsSection = 'files';
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
      session.activePage = 'settings';
      settingsSection = 'files';
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
      session.activePage = 'settings';
      settingsSection = 'monitoring';
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
    session.activePage = 'settings';
    settingsSection = 'monitoring';
    render();
  }

  function renderAbout() {
    const version = escapeHtml(session.data.application?.version || '2.2.0');
    viewRoot.innerHTML = `
      <section class="about-view">
        <div class="settings-heading">
          <div>
            <h2>Sobre o projeto</h2>
            <span class="text-small text-muted">Identidade, autoria e repositório oficial do Santri Exportações.</span>
          </div>
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
      history_retention_days: Number(document.getElementById('setting-history-retention').value),
      artifact_retention_days: Number(document.getElementById('setting-artifact-retention').value),
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

  async function run(ids, action, source = 'manual', temporaryOptions = null) {
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
      const result = await api().run_workflows(session.activeCompany, ids, action, source, '', temporaryOptions || {});
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
        entries: value.entries.map(entry => ({weekday: Number(entry.weekday), time: String(entry.time || '')})),
        exceptions: Array.isArray(value.exceptions) ? value.exceptions : [],
        priority: Number(value.priority || 3),
        max_attempts: Number(value.max_attempts || 3),
        retry_failed_stage: value.retry_failed_stage !== false
      };
    }
    const text = String(value || '');
    const time = text.match(/\b(?:[01]\d|2[0-3]):[0-5]\d\b/)?.[0];
    if (!time || text.toLowerCase() === 'manual' || text.toLowerCase() === 'desligado') return {enabled: false, entries: [], exceptions: [], priority: 3, max_attempts: 3, retry_failed_stage: true};
    const weekdays = text.toLowerCase().includes('diariamente') ? [0, 1, 2, 3, 4, 5, 6] : [0, 1, 2, 3, 4];
    return {enabled: true, entries: weekdays.map(weekday => ({weekday, time})), exceptions: [], priority: 3, max_attempts: 3, retry_failed_stage: true};
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
    document.getElementById('schedule-priority').value = String(schedule.priority || 3);
    document.getElementById('schedule-attempts').value = String(schedule.max_attempts || 3);
    document.getElementById('schedule-retry-stage').checked = schedule.retry_failed_stage !== false;
    exceptionDateEditor.load(schedule.exceptions || []);
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
    const exceptions = exceptionDateEditor.value();
    return {enabled, entries, exceptions, priority: Number(document.getElementById('schedule-priority').value), max_attempts: Number(document.getElementById('schedule-attempts').value), retry_failed_stage: document.getElementById('schedule-retry-stage').checked};
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
    document.getElementById('run-temporary-company').hidden = !item?.implemented;
    document.getElementById('report-name').value = item?.name || '';
    document.getElementById('report-name').disabled = Boolean(item?.implemented);
    document.getElementById('report-description').value = item?.description || '';
    const lifecycle = document.getElementById('workflow-lifecycle');
    lifecycle.value = item?.lifecycle || (item?.implemented ? 'production' : 'draft');
    lifecycle.querySelector('option[value="draft"]').disabled = Boolean(item?.implemented);
    document.getElementById('workflow-version-button').hidden = !item?.id;
    document.getElementById('workflow-version-list').hidden = true;
    document.getElementById('workflow-version-list').innerHTML = '';
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
    customSelects.refresh(editor);
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
  document.getElementById('workflow-version-button').addEventListener('click', loadWorkflowVersions);
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

  async function loadWorkflowVersions() {
    const workflowId = document.getElementById('workflow-id').value;
    if (!workflowId) return;
    const container = document.getElementById('workflow-version-list');
    try {
      const versions = await api().list_workflow_versions(session.activeCompany, workflowId);
      container.hidden = false;
      container.innerHTML = versions.length ? versions.map(version => `<article><span><strong>${escapeHtml(version.reason || 'Configuração salva')}</strong><small>${escapeHtml(new Date(version.timestamp).toLocaleString('pt-BR'))} · ${escapeHtml(String(version.sha256 || '').slice(0, 12))}</small></span><button class="btn restore-workflow-version" data-version="${escapeHtml(version.id)}" type="button">Restaurar</button></article>`).join('') : '<div class="empty">A primeira versão será criada ao salvar esta configuração.</div>';
      container.querySelectorAll('.restore-workflow-version').forEach(button => button.addEventListener('click', restoreWorkflowVersion));
    } catch (error) {
      showToast('Histórico indisponível', String(error.message || error), true);
    }
  }

  async function restoreWorkflowVersion(event) {
    const workflowId = document.getElementById('workflow-id').value;
    const confirmed = await requestConfirmation({title: 'Restaurar esta configuração?', message: 'O estado atual será versionado antes da restauração. A operação ficará registrada no histórico.', confirmLabel: 'Restaurar versão'});
    if (!confirmed) return;
    try {
      await api().restore_workflow_version(session.activeCompany, workflowId, event.currentTarget.dataset.version);
      await loadState();
      openEditor(workflowId);
      showToast('Versão restaurada', 'A configuração anterior foi restaurada com integridade verificada.', false);
    } catch (error) {
      showToast('Restauração bloqueada', String(error.message || error), true);
    }
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
      enabled: true,
      lifecycle: document.getElementById('workflow-lifecycle').value
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
  document.getElementById('run-temporary-company').addEventListener('click', async () => {
    const workflowId = document.getElementById('workflow-id').value;
    if (!workflowId) return;
    const confirmed = await requestConfirmation({title: 'Executar com parâmetros temporários?', message: 'Destino, prefixo, período, filtros e tentativas serão usados somente nesta execução e não serão salvos no catálogo.', confirmLabel: 'Executar sem salvar'});
    if (!confirmed) return;
    const dateRange = collectDateRange();
    const stockFilter = collectStockFilter();
    const temporaryOptions = {
      destination: document.getElementById('destination-path').value,
      filename_prefix: document.getElementById('filename-prefix').value,
      max_attempts: Number(document.getElementById('schedule-attempts').value),
      timeout_minutes: Number(session.data.settings?.timeout_minutes || 10)
    };
    if (dateRange) temporaryOptions.date_range = dateRange;
    if (stockFilter !== null) temporaryOptions.include_asset_consumption = stockFilter;
    session.editorDirty = false;
    closeEditor();
    await run([workflowId], 'all', 'manual_temporary', temporaryOptions);
  });

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

  document.getElementById('home-button').addEventListener('click', async () => {
    if (session.activePage === 'dashboard') return;
    if (!await confirmPendingChanges()) return;
    showDashboard();
    closeEditor();
    progressCard.classList.remove('visible');
  });
  document.getElementById('history-button').addEventListener('click', async () => {
    if (!await confirmPendingChanges()) return;
    session.activePage = 'history';
    closeEditor();
    progressCard.classList.remove('visible');
    render();
  });
  document.getElementById('platform-button').addEventListener('click', async () => {
    if (!await confirmPendingChanges()) return;
    session.activePage = 'platform';
    platformSimulation = null;
    closeEditor();
    progressCard.classList.remove('visible');
    await loadState();
    session.activePage = 'platform';
    render();
  });
  document.getElementById('schedule-button').addEventListener('click', async () => {
    if (!await confirmPendingChanges()) return;
    session.activePage = 'schedule';
    closeEditor();
    progressCard.classList.remove('visible');
    render();
  });
  document.getElementById('reliability-button').addEventListener('click', async () => {
    if (!await confirmPendingChanges()) return;
    session.activePage = 'reliability';
    closeEditor();
    progressCard.classList.remove('visible');
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
  setInterval(async () => {
    if (session.activePage !== 'platform' || !api()?.get_execution_queue) return;
    try {
      const queue = await api().get_execution_queue();
      if (session.data.application?.platform) session.data.application.platform.queue = queue;
      renderPlatform();
    } catch (_error) {
      return;
    }
  }, 2000);

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
          if (session.data.application?.release?.automatic_check) {
            setTimeout(async () => {
              try {
                releaseCheck = await api().check_for_updates(session.data.application.release.channel);
                if (releaseCheck?.available) showToast('Atualização disponível', `A versão ${releaseCheck.latest_version} está disponível no canal configurado.`, false);
              } catch (error) {
                releaseCheck = {ok: false, error: String(error.message || error)};
              }
            }, 1200);
          }
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
