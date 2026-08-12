export class DashboardSession {
  constructor(initialState) {
    this.data = initialState;
    this.activeCompany = 'sol';
    this.activePage = 'dashboard';
    this.initialized = false;
    this.busy = false;
    this.settingsDirty = false;
    this.editorDirty = false;
    this.progressStep = 0;
    this.historyCompany = 'all';
    this.historyCategory = 'all';
    this.historyStatus = 'all';
    this.historySearch = '';
    this.latestDiagnostic = null;
    this.startupFinished = false;
    this.bridgeInitializing = false;
  }
}
