export class CustomSelectService {
  constructor(documentRoot) {
    this.document = documentRoot;
    this.controls = new Map();
    this.observer = new MutationObserver(records => this.handleMutations(records));
    this.handleDocumentClick = event => {
      if (!event.target.closest('.custom-select')) this.closeAll();
    };
    this.handleDocumentKeydown = event => {
      if (event.key === 'Escape') this.closeAll(true);
    };
  }

  start() {
    this.enhance(this.document);
    this.observer.observe(this.document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['disabled']});
    this.document.addEventListener('click', this.handleDocumentClick);
    this.document.addEventListener('keydown', this.handleDocumentKeydown);
  }

  enhance(root) {
    const selects = [];
    if (root instanceof HTMLSelectElement) selects.push(root);
    if (root.querySelectorAll) selects.push(...root.querySelectorAll('select.form-select:not([data-custom-select])'));
    for (const select of selects) this.create(select);
  }

  create(select) {
    if (this.controls.has(select)) return;
    const wrapper = this.document.createElement('span');
    wrapper.className = 'custom-select';
    const trigger = this.document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'custom-select-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    const label = this.document.createElement('span');
    const chevron = this.document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chevron.setAttribute('viewBox', '0 0 24 24');
    chevron.setAttribute('aria-hidden', 'true');
    const chevronPath = this.document.createElementNS('http://www.w3.org/2000/svg', 'path');
    chevronPath.setAttribute('d', 'm7 10 5 5 5-5');
    chevron.append(chevronPath);
    trigger.append(label, chevron);
    const options = this.document.createElement('span');
    options.className = 'custom-select-options';
    options.setAttribute('role', 'listbox');
    options.hidden = true;
    select.before(wrapper);
    wrapper.append(select, trigger, options);
    select.dataset.customSelect = 'true';
    select.classList.add('custom-select-native');
    select.tabIndex = -1;
    const control = {select, wrapper, trigger, label, options};
    this.controls.set(select, control);
    trigger.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      this.toggle(control);
    });
    trigger.addEventListener('keydown', event => this.handleTriggerKeydown(event, control));
    select.addEventListener('change', () => this.refreshControl(control));
    this.refreshControl(control);
  }

  refresh(root = this.document) {
    this.enhance(root);
    for (const control of this.controls.values()) {
      if (root === this.document || root.contains?.(control.select) || root === control.select) this.refreshControl(control);
    }
  }

  refreshControl(control) {
    const {select, trigger, label} = control;
    const selected = select.options[select.selectedIndex];
    label.textContent = selected?.textContent?.trim() || 'Selecione';
    trigger.disabled = select.disabled;
    trigger.setAttribute('aria-label', label.textContent);
    this.renderOptions(control);
  }

  renderOptions(control) {
    const {select, options} = control;
    options.replaceChildren();
    [...select.options].forEach((option, index) => {
      const button = this.document.createElement('button');
      button.type = 'button';
      button.className = 'custom-select-option';
      button.setAttribute('role', 'option');
      button.setAttribute('aria-selected', String(index === select.selectedIndex));
      button.classList.toggle('is-selected', index === select.selectedIndex);
      button.disabled = option.disabled;
      button.textContent = option.textContent.trim();
      button.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        this.select(control, index);
      });
      button.addEventListener('keydown', event => {
        if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
        event.preventDefault();
        this.moveOptionFocus(control, event.key === 'ArrowDown' ? 1 : -1);
      });
      options.append(button);
    });
  }

  toggle(control) {
    if (control.select.disabled) return;
    const opening = control.options.hidden;
    this.closeAll();
    if (!opening) return;
    control.options.hidden = false;
    control.wrapper.classList.add('is-open');
    control.trigger.setAttribute('aria-expanded', 'true');
    this.position(control);
  }

  position(control) {
    control.wrapper.classList.remove('opens-up');
    const triggerRect = control.trigger.getBoundingClientRect();
    const availableBelow = globalThis.innerHeight - triggerRect.bottom;
    if (availableBelow < Math.min(control.options.scrollHeight + 12, 260) && triggerRect.top > availableBelow) {
      control.wrapper.classList.add('opens-up');
    }
  }

  select(control, index) {
    if (control.select.options[index]?.disabled) return;
    control.select.selectedIndex = index;
    control.select.dispatchEvent(new Event('input', {bubbles: true}));
    control.select.dispatchEvent(new Event('change', {bubbles: true}));
    this.close(control, true);
  }

  handleTriggerKeydown(event, control) {
    if (!['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    if (control.options.hidden) {
      this.toggle(control);
      this.focusSelected(control);
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') this.moveOptionFocus(control, event.key === 'ArrowDown' ? 1 : -1);
  }

  focusSelected(control) {
    const selected = control.options.querySelector('.is-selected:not(:disabled)');
    const first = control.options.querySelector('.custom-select-option:not(:disabled)');
    (selected || first)?.focus();
  }

  moveOptionFocus(control, direction) {
    const enabled = [...control.options.querySelectorAll('.custom-select-option:not(:disabled)')];
    if (!enabled.length) return;
    const current = enabled.indexOf(this.document.activeElement);
    enabled[(current + direction + enabled.length) % enabled.length].focus();
  }

  close(control, restoreFocus = false) {
    control.options.hidden = true;
    control.wrapper.classList.remove('is-open', 'opens-up');
    control.trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus) control.trigger.focus();
  }

  closeAll(restoreFocus = false) {
    for (const control of this.controls.values()) {
      if (!control.options.hidden) this.close(control, restoreFocus);
    }
  }

  handleMutations(records) {
    for (const record of records) {
      if (record.type === 'attributes' && this.controls.has(record.target)) this.refreshControl(this.controls.get(record.target));
      for (const node of record.addedNodes) {
        if (node instanceof Element) this.enhance(node);
      }
    }
  }
}
