export class AppearanceService {
  constructor(root) {
    this.root = root;
  }

  apply(settings = {}) {
    this.root.dataset.theme = settings.theme === 'dark' ? 'dark' : 'light';
  }
}
