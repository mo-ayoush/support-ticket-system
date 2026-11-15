import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const mocks = vi.hoisted(() => ({
  currentUser: vi.fn(), list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(),
  requestStatus: vi.fn(), operationStatus: vi.fn(), audit: vi.fn(), dlq: vi.fn(),
}));
vi.mock('../src/services/auth', () => ({ currentUser: mocks.currentUser, login: vi.fn(), logout: vi.fn() }));
vi.mock('../src/services/api', () => ({
  api: { list: mocks.list, get: mocks.get, create: mocks.create, update: mocks.update, remove: mocks.remove, requestStatus: mocks.requestStatus, operationStatus: mocks.operationStatus, audit: mocks.audit, dlq: mocks.dlq },
  ApiError: class extends Error { status = 500; },
}));
import App from '../src/App';

const agent = { sub: 'sub-agent', email: 'agent@example.test', groups: ['SupportUsers'] };
beforeEach(() => { vi.clearAllMocks(); });

describe('authenticated frontend flows', () => {
  it('shows Cognito sign-in when there is no authenticated session', async () => {
    mocks.currentUser.mockResolvedValue(null);
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: /make every issue/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continue with secure sign in/i })).toBeInTheDocument();
  });

  it('shows a data-backed dashboard for an authenticated support user', async () => {
    mocks.currentUser.mockResolvedValue(agent);
    mocks.list.mockResolvedValue({ tickets: [{ ticket_id:'id-1',title:'Cannot access email',description:'Email issue',priority:'CRITICAL',status:'OPEN',created_by:'sub-agent',created_at:'2026-11-14T10:00:00Z',updated_at:'2026-11-14T10:00:00Z',version:1 }] });
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: /good (morning|afternoon), agent/i })).toBeInTheDocument();
    expect(await screen.findByText('Cannot access email')).toBeInTheDocument();
    expect(screen.getByText('Needs attention')).toBeInTheDocument();
    expect(mocks.list).toHaveBeenCalledWith({ limit: 50, next_token: undefined });
  });

  it('submits a new ticket and communicates that 202 means processing', async () => {
    mocks.currentUser.mockResolvedValue(agent);
    mocks.create.mockResolvedValue({ ticket_id: 'ticket-42', status: 'SENT' });
    mocks.requestStatus.mockReturnValue(new Promise(() => undefined));
    render(<MemoryRouter initialEntries={['/tickets/new']}><App /></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: 'Create a ticket' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/title/i), { target: { value: 'Cannot access email' } });
    fireEvent.change(screen.getByLabelText(/description/i), { target: { value: 'Email login fails for the whole team.' } });
    fireEvent.click(screen.getByRole('button', { name: /submit ticket/i }));
    expect(await screen.findByText(/operation sent · ticket-42/i)).toBeInTheDocument();
    expect(mocks.create).toHaveBeenCalledWith({ title: 'Cannot access email', description: 'Email login fails for the whole team.', priority: 'MEDIUM', status: 'OPEN' }, expect.any(String));
  });
});
