import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ signOut: vi.fn(async () => undefined), setStorage: vi.fn() }));
vi.mock('@aws-amplify/core', () => ({ Amplify: { configure: vi.fn() } }));
vi.mock('@aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(), fetchUserAttributes: vi.fn(), getCurrentUser: vi.fn(),
  signInWithRedirect: vi.fn(), signOut: mocks.signOut,
}));
vi.mock('aws-amplify/auth/cognito', () => ({ cognitoUserPoolsTokenProvider: { setKeyValueStorage: mocks.setStorage } }));

import { logout } from '../src/services/auth';
import { saveOperation } from '../src/services/operations';

afterEach(() => { sessionStorage.clear(); vi.clearAllMocks(); });

describe('logout cleanup', () => {
  it('removes persisted ticket retry payloads before signing out', async () => {
    saveOperation({operation_id:'logout-key-0001',idempotency_key:'logout-key-0001',owner_sub:'user-1',fingerprint:'f',kind:'CREATE',status:'PENDING',updated_at:'now'},
      {method:'CREATE',body:{title:'Sensitive',description:'Private details',priority:'HIGH'}});
    sessionStorage.setItem('unrelated-session-value','keep');
    await logout();
    expect(sessionStorage.getItem('techassist.operation-request.v1:logout-key-0001')).toBeNull();
    expect(sessionStorage.getItem('unrelated-session-value')).toBe('keep');
    expect(mocks.signOut).toHaveBeenCalledOnce();
  });
});
