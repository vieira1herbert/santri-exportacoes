export class BridgeClient {
  constructor(host) {
    this.host = host;
  }

  get api() {
    return this.host.pywebview?.api;
  }

  async getState() {
    if (!this.api?.get_state) throw new Error('A ponte com o agente Windows não está disponível.');
    return this.api.get_state();
  }

  isReady() {
    return Boolean(this.api?.get_state);
  }
}
