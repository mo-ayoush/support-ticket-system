export type OperationKind = 'CREATE' | 'UPDATE' | 'DELETE';
export type OperationStatus = 'PENDING' | 'COMPLETED' | 'FAILED' | 'AMBIGUOUS';
export interface OperationRequest {
  method: OperationKind;
  ticket_id?: string;
  version?: number;
  body: Record<string, unknown>;
}
export interface StoredOperation {
  operation_id: string;
  idempotency_key: string;
  owner_sub: string;
  fingerprint: string;
  kind: OperationKind;
  ticket_id?: string;
  status: OperationStatus;
  message?: string;
  updated_at: string;
}

const INDEX_KEY = 'techassist.operation-index.v1';
const OPERATION_PREFIX = 'techassist.operation.v1:';
const REQUEST_PREFIX = 'techassist.operation-request.v1:';

function readIndex(): StoredOperation[] {
  const rows = new Map<string, StoredOperation>();
  // Read legacy index data first for an incremental migration. Each new record
  // is stored under its own key, so two tabs adding different operations cannot
  // overwrite one another with competing read-modify-write array snapshots.
  try {
    const legacy = JSON.parse(localStorage.getItem(INDEX_KEY) || '[]');
    if (Array.isArray(legacy)) {
      for (const row of legacy) if (row?.operation_id) rows.set(row.operation_id, row as StoredOperation);
    }
  } catch { /* Ignore a damaged legacy index and recover individual records. */ }
  for (let index = 0; index < localStorage.length; index++) {
    const key = localStorage.key(index);
    if (!key?.startsWith(OPERATION_PREFIX)) continue;
    try {
      const row = JSON.parse(localStorage.getItem(key) || 'null') as StoredOperation | null;
      if (row?.operation_id) rows.set(row.operation_id, row);
    } catch { /* Ignore a damaged individual row and retain other operations. */ }
  }
  return [...rows.values()];
}
function writeIndex(rows: StoredOperation[]) {
  const active = rows.filter(row => row.status === 'PENDING' || row.status === 'AMBIGUOUS');
  const finished = rows.filter(row => row.status === 'COMPLETED' || row.status === 'FAILED')
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  // Keep every actionable record, even when that means history exceeds 50 rows.
  const retained = [...finished.slice(0, Math.max(0, 50 - active.length)), ...active];
  const retainedIds = new Set(retained.map(row => row.operation_id));
  for (const row of retained) {
    const key = `${OPERATION_PREFIX}${encodeURIComponent(row.operation_id)}`;
    const existing = readStoredOperation(key);
    const value = existing ? mergeOperation(existing, row) : row;
    localStorage.setItem(key, JSON.stringify(value));
  }
  // Only prune terminal history. A pending operation created concurrently in
  // another tab is never removed, even if it was absent from this tab's read.
  for (let index = localStorage.length - 1; index >= 0; index--) {
    const key = localStorage.key(index);
    if (!key?.startsWith(OPERATION_PREFIX)) continue;
    const row = readStoredOperation(key);
    if (row && (row.status === 'COMPLETED' || row.status === 'FAILED') && !retainedIds.has(row.operation_id)) {
      localStorage.removeItem(key);
    }
  }
  localStorage.removeItem(INDEX_KEY);
}
function readStoredOperation(key: string): StoredOperation | undefined {
  try {
    const row = JSON.parse(localStorage.getItem(key) || 'null') as StoredOperation | null;
    return row?.operation_id ? row : undefined;
  } catch { return undefined; }
}
function mergeOperation(existing: StoredOperation, incoming: StoredOperation): StoredOperation {
  if (existing.status === 'COMPLETED' && incoming.status !== 'COMPLETED') return existing;
  if (existing.status === 'FAILED' && incoming.status !== 'COMPLETED' && incoming.status !== 'FAILED') return existing;
  if (existing.status === 'AMBIGUOUS' && incoming.status === 'PENDING' && !incoming.message?.startsWith('SQS_REJECTED:') && !incoming.message?.startsWith('Retrying with the original idempotency key.')) return existing;
  return incoming;
}
function nextUpdatedAt(previous?: string) {
  const parsed = previous ? Date.parse(previous) : 0;
  return new Date(Math.max(Date.now(), Number.isFinite(parsed) ? parsed + 1 : 0)).toISOString();
}
export function listOperations(ownerSub: string): StoredOperation[] {
  return readIndex().filter(row => row.owner_sub === ownerSub).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}
export function findReusableOperation(ownerSub: string, fingerprint: string): StoredOperation | undefined {
  return listOperations(ownerSub).find(row => row.fingerprint === fingerprint &&
    (row.status === 'PENDING' || row.status === 'AMBIGUOUS'));
}
export function saveOperation(row: StoredOperation, request?: OperationRequest) {
  const current = readIndex();
  const previous = current.find(item => item.operation_id === row.operation_id)?.updated_at;
  const rows = current.filter(item => item.operation_id !== row.operation_id);
  rows.push({ ...row, updated_at: nextUpdatedAt(previous) });
  writeIndex(rows);
  if (request) sessionStorage.setItem(`${REQUEST_PREFIX}${row.operation_id}`, JSON.stringify(request));
}
export function getOperationRequest(operationId: string): OperationRequest | undefined {
  try {
    const value = sessionStorage.getItem(`${REQUEST_PREFIX}${operationId}`);
    return value ? JSON.parse(value) as OperationRequest : undefined;
  } catch { return undefined; }
}
export function clearOperationRequests() {
  for (let index = sessionStorage.length - 1; index >= 0; index--) {
    const key = sessionStorage.key(index);
    if (key?.startsWith(REQUEST_PREFIX)) sessionStorage.removeItem(key);
  }
}
export function updateOperation(operationId: string, update: Partial<Pick<StoredOperation, 'status' | 'ticket_id' | 'message'>>) {
  const rows = readIndex().map(row => {
    if (row.operation_id !== operationId) return row;
    if (row.status === 'COMPLETED' && update.status && update.status !== 'COMPLETED') return row;
    if (row.status === 'FAILED' && update.status && update.status !== 'COMPLETED' && update.status !== 'FAILED') return row;
    if (row.status === 'AMBIGUOUS' && update.status === 'PENDING' && !update.message?.startsWith('SQS_REJECTED:') && !update.message?.startsWith('Retrying with the original idempotency key.')) return row;
    return { ...row, ...update, updated_at: nextUpdatedAt(row.updated_at) };
  });
  writeIndex(rows);
  if (update.status === 'COMPLETED' || update.status === 'FAILED') {
    sessionStorage.removeItem(`${REQUEST_PREFIX}${operationId}`);
  }
}
export function statusFromServer(status: string): OperationStatus {
  if (status === 'COMPLETED') return 'COMPLETED';
  if (status === 'FAILED' || status === 'CONFLICT') return 'FAILED';
  if (status === 'AMBIGUOUS') return 'AMBIGUOUS';
  return 'PENDING';
}
