export class DomRegistry {
  constructor(root) {
    this.root = root;
  }

  byId(id) {
    const element = this.root.getElementById(id);
    if (!element) throw new Error(`Elemento obrigatório não encontrado: ${id}`);
    return element;
  }
}
