import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../src/services/api';

vi.mock('../src/services/auth', () => ({ accessToken: vi.fn(async () => 'test-access-token') }));
const fetchMock = vi.fn();
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals(); });

describe('central API service', () => {
  it('posts ticket data with access token and idempotency key and accepts 202', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/v1');
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ operation_id: 'stable-key', ticket_id: 'ticket-123', status: 'SENT' }), { status: 202 }));
    vi.stubGlobal('fetch', fetchMock);
    const result = await api.create({ title: 'Help', description: 'Email issue', priority: 'HIGH' });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://api.example.test/v1/tickets');
    expect(new Headers(init.headers).get('Authorization')).toBe('test-access-token');
    expect(new Headers(init.headers).get('Idempotency-Key')).toMatch(/^[0-9a-f-]{36}$/i);
    expect(result.status).toBe('SENT');
  });

  it('preserves the backend conflict status and message', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/v1');
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ error: 'Ticket version conflict' }), { status: 409 }));
    vi.stubGlobal('fetch', fetchMock);
    await expect(api.list()).rejects.toMatchObject({ status: 409, message: 'Ticket version conflict' });
  });

  it('looks up one exact operation by its idempotency key', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/v1');
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ operation_id: 'stable-key', ticket_id: 'ticket-123', status: 'COMPLETED' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const result = await api.operationStatus('stable-key');
    expect(result.operation_id).toBe('stable-key');
    expect(fetchMock.mock.calls[0][0]).toBe('https://api.example.test/v1/requests/stable-key');
  });
});
