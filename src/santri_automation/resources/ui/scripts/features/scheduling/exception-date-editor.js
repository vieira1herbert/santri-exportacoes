export class ExceptionDateEditor {
  constructor(elements, onChange) {
    Object.assign(this, elements);
    this.onChange = onChange;
    this.dates = [];
    this.selectedDate = '';
    const today = new Date();
    this.viewYear = today.getFullYear();
    this.viewMonth = today.getMonth();
    this.trigger.addEventListener('click', () => this.toggleCalendar());
    this.addButton.addEventListener('click', () => this.addSelectedDate());
    this.previousButton.addEventListener('click', () => this.changeMonth(-1));
    this.nextButton.addEventListener('click', () => this.changeMonth(1));
    this.todayButton.addEventListener('click', () => this.selectToday());
    this.clearButton.addEventListener('click', () => this.clearSelection());
    this.grid.addEventListener('click', event => this.selectCalendarDay(event));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') this.closeCalendar();
    });
    this.render();
  }

  load(exceptions = []) {
    this.dates = [...new Set(exceptions
      .filter(item => item?.action === 'skip' && this.isIsoDate(item.date))
      .map(item => item.date))].sort();
    this.clearSelection();
    this.render();
  }

  value() {
    return this.dates.map(date => ({date, action: 'skip'}));
  }

  toggleCalendar() {
    const opening = this.calendar.hidden;
    this.calendar.hidden = !opening;
    this.trigger.setAttribute('aria-expanded', String(opening));
    if (opening) this.renderCalendar();
  }

  closeCalendar() {
    this.calendar.hidden = true;
    this.trigger.setAttribute('aria-expanded', 'false');
  }

  changeMonth(offset) {
    const target = new Date(this.viewYear, this.viewMonth + offset, 1, 12);
    this.viewYear = target.getFullYear();
    this.viewMonth = target.getMonth();
    this.renderCalendar();
  }

  selectToday() {
    const today = new Date();
    this.selectDate(this.toIsoDate(today.getFullYear(), today.getMonth(), today.getDate()));
  }

  clearSelection() {
    this.selectedDate = '';
    this.valueLabel.textContent = 'Selecionar uma data';
    this.trigger.classList.remove('has-value');
    this.addButton.disabled = true;
    this.renderCalendar();
  }

  selectCalendarDay(event) {
    const button = event.target.closest('[data-date]');
    if (!button) return;
    this.selectDate(button.dataset.date);
  }

  selectDate(date) {
    if (!this.isIsoDate(date)) return;
    this.selectedDate = date;
    const [year, month] = date.split('-').map(Number);
    this.viewYear = year;
    this.viewMonth = month - 1;
    this.valueLabel.textContent = this.formatBrazilian(date);
    this.trigger.classList.add('has-value');
    this.addButton.disabled = false;
    this.renderCalendar();
  }

  addSelectedDate() {
    if (!this.isIsoDate(this.selectedDate)) return;
    if (!this.dates.includes(this.selectedDate)) {
      this.dates.push(this.selectedDate);
      this.dates.sort();
      this.onChange();
    }
    this.clearSelection();
    this.closeCalendar();
    this.renderList();
  }

  remove(date) {
    const next = this.dates.filter(item => item !== date);
    if (next.length === this.dates.length) return;
    this.dates = next;
    this.render();
    this.onChange();
  }

  render() {
    this.renderCalendar();
    this.renderList();
  }

  renderCalendar() {
    const monthName = new Intl.DateTimeFormat('pt-BR', {month: 'long', year: 'numeric'})
      .format(new Date(this.viewYear, this.viewMonth, 1, 12));
    this.monthLabel.textContent = monthName.charAt(0).toUpperCase() + monthName.slice(1);
    this.grid.replaceChildren();
    const firstWeekday = new Date(this.viewYear, this.viewMonth, 1, 12).getDay();
    const start = new Date(this.viewYear, this.viewMonth, 1 - firstWeekday, 12);
    const today = new Date();
    const todayIso = this.toIsoDate(today.getFullYear(), today.getMonth(), today.getDate());
    for (let index = 0; index < 42; index += 1) {
      const current = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index, 12);
      const isoDate = this.toIsoDate(current.getFullYear(), current.getMonth(), current.getDate());
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.date = isoDate;
      button.textContent = String(current.getDate());
      button.className = 'exception-calendar-day';
      button.classList.toggle('outside-month', current.getMonth() !== this.viewMonth);
      button.classList.toggle('today', isoDate === todayIso);
      button.classList.toggle('selected', isoDate === this.selectedDate);
      button.classList.toggle('configured', this.dates.includes(isoDate));
      button.setAttribute('aria-label', this.formatBrazilian(isoDate));
      button.setAttribute('aria-pressed', String(isoDate === this.selectedDate));
      this.grid.append(button);
    }
  }

  renderList() {
    this.list.replaceChildren();
    for (const date of this.dates) {
      const chip = document.createElement('span');
      chip.className = 'exception-date-chip';
      const label = document.createElement('span');
      label.textContent = this.formatBrazilian(date);
      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.setAttribute('aria-label', `Remover exceção de ${label.textContent}`);
      removeButton.textContent = '×';
      removeButton.addEventListener('click', () => this.remove(date));
      chip.append(label, removeButton);
      this.list.append(chip);
    }
    this.emptyState.hidden = this.dates.length > 0;
  }

  isIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ''))) return false;
    const [year, month, day] = value.split('-').map(Number);
    const parsed = new Date(Date.UTC(year, month - 1, day));
    return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day;
  }

  toIsoDate(year, zeroBasedMonth, day) {
    return `${String(year).padStart(4, '0')}-${String(zeroBasedMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  }

  formatBrazilian(value) {
    const [year, month, day] = value.split('-');
    return `${day}/${month}/${year}`;
  }
}
