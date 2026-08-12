export class PageRouter {
  constructor() {
    this.routes = new Map();
  }

  register(name, renderer) {
    this.routes.set(name, renderer);
    return this;
  }

  render(name) {
    const renderer = this.routes.get(name);
    if (!renderer) throw new Error(`Tela não registrada: ${name}`);
    renderer();
  }
}
