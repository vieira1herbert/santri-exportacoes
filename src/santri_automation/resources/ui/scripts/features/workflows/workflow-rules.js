export class WorkflowRules {
  hasFailure(value) {
    const normalized = String(value || '').toLowerCase();
    return ['falha', 'erro', 'bloquead'].some(term => normalized.includes(term));
  }

  isTransfer(id, name) {
    return id === 'transfer_ncias' || String(name || '').toLowerCase().includes('transfer');
  }

  isStock(id, name) {
    return id === 'estoque_disponivel' || String(name || '').toLowerCase().includes('estoque dispon');
  }
}
