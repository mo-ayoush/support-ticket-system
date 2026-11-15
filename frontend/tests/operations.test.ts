import { afterEach, describe, expect, it } from 'vitest';
import { clearOperationRequests, findReusableOperation, getOperationRequest, listOperations, saveOperation, statusFromServer, updateOperation, type StoredOperation } from '../src/services/operations';

afterEach(()=>{localStorage.clear();sessionStorage.clear();});

describe('durable operation storage',()=>{
  const row:StoredOperation={operation_id:'stable-key',idempotency_key:'stable-key',owner_sub:'user-1',fingerprint:'same-request',kind:'CREATE',status:'PENDING',updated_at:'2026-01-01T00:00:00Z'};
  it('persists the operation ID and idempotency key and reuses the same key for unchanged work',()=>{
    saveOperation(row,{method:'CREATE',body:{title:'Issue',description:'Details',priority:'HIGH'}});
    expect(listOperations('user-1')[0].operation_id).toBe('stable-key');
    expect(findReusableOperation('user-1','same-request')?.idempotency_key).toBe('stable-key');
    expect(getOperationRequest('stable-key')?.body.title).toBe('Issue');
    expect(listOperations('other-user')).toEqual([]);
  });
  it('represents all server operation outcomes',()=>{
    expect(statusFromServer('PENDING')).toBe('PENDING');
    expect(statusFromServer('SENT')).toBe('PENDING');
    expect(statusFromServer('COMPLETED')).toBe('COMPLETED');
    expect(statusFromServer('FAILED')).toBe('FAILED');
    expect(statusFromServer('AMBIGUOUS')).toBe('AMBIGUOUS');
    saveOperation(row); updateOperation('stable-key',{status:'AMBIGUOUS'});
    expect(listOperations('user-1')[0].status).toBe('AMBIGUOUS');
  });
  it('retains every pending operation when terminal history exceeds its limit',()=>{
    for(let i=0;i<60;i++)saveOperation({...row,operation_id:`done-${i}`,idempotency_key:`done-${i}`,status:'COMPLETED',updated_at:`2026-01-${String((i%28)+1).padStart(2,'0')}T00:00:00Z`});
    for(let i=0;i<55;i++)saveOperation({...row,operation_id:`pending-${i}`,idempotency_key:`pending-${i}`,status:'PENDING'});
    expect(listOperations('user-1').filter(op=>op.status==='PENDING')).toHaveLength(55);
    expect(listOperations('user-1').filter(op=>op.status==='COMPLETED')).toHaveLength(0);
  });
  it('merges independent per-operation writes with a stale legacy tab index',()=>{
    const first={...row,operation_id:'tab-one-key',idempotency_key:'tab-one-key'};
    const second={...row,operation_id:'tab-two-key',idempotency_key:'tab-two-key'};
    const third={...row,operation_id:'tab-three-key',idempotency_key:'tab-three-key'};
    saveOperation(second);
    // Simulate a still-open older tab writing its pre-migration index snapshot.
    localStorage.setItem('techassist.operation-index.v1',JSON.stringify([first]));
    saveOperation(third);
    expect(listOperations('user-1').map(op=>op.operation_id).sort()).toEqual([
      'tab-one-key','tab-three-key','tab-two-key',
    ]);
    expect(listOperations('user-1').every(op=>op.status==='PENDING')).toBe(true);
    expect(localStorage.getItem('techassist.operation-index.v1')).toBeNull();
  });
  it('clears retry payloads without clearing unrelated session data on logout cleanup',()=>{
    saveOperation(row,{method:'CREATE',body:{title:'Private issue',description:'Private details',priority:'HIGH'}});
    sessionStorage.setItem('auth-token-cache','preserve');
    clearOperationRequests();
    expect(getOperationRequest(row.operation_id)).toBeUndefined();
    expect(sessionStorage.getItem('auth-token-cache')).toBe('preserve');
  });
});
