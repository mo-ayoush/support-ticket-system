import { accessToken } from './auth';
import type { AuditEvent, RequestState, Ticket, TicketPage } from '../types';

const apiBase = () => (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '');
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const base = apiBase();
  if (!base) throw new Error('Set VITE_API_BASE_URL in frontend/.env.local.');
  const token = await accessToken();
  const headers = new Headers(init.headers);
  headers.set('Authorization', token);
  if (init.body) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${base}${path}`, { ...init, headers });
  const text = await response.text();
  let data: any = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text }; }
  if (!response.ok) throw new ApiError(data.error ?? `Request failed (${response.status})`, response.status);
  return data as T;
}
const query = (params: Record<string, string | number | undefined>) => {
  const qs = new URLSearchParams(); Object.entries(params).forEach(([k,v]) => v !== undefined && qs.set(k,String(v)));
  return qs.size ? `?${qs}` : '';
};
export const api = {
  list: (params: { limit?:number; next_token?:string } = {}) => request<TicketPage>(`/tickets${query(params)}`),
  get: (id: string) => request<Ticket>(`/tickets/${encodeURIComponent(id)}`),
  create: (body: {title:string;description:string;priority:string;status?:string}, idempotencyKey: string=crypto.randomUUID()) => request<{operation_id:string;ticket_id:string;status:string}>('/tickets',{method:'POST',headers:{'Idempotency-Key':idempotencyKey},body:JSON.stringify(body)}),
  update: (ticket: Ticket, body: {title:string;description:string;priority:string;status:string}, idempotencyKey: string=crypto.randomUUID()) => request<{operation_id:string;ticket_id:string;status:string}>(`/tickets/${encodeURIComponent(ticket.ticket_id)}`,{method:'PUT',headers:{'Idempotency-Key':idempotencyKey},body:JSON.stringify({...body,version:ticket.version})}),
  remove: (ticket: Ticket, idempotencyKey: string=crypto.randomUUID()) => request<{operation_id:string;ticket_id:string;status:string}>(`/tickets/${encodeURIComponent(ticket.ticket_id)}`,{method:'DELETE',headers:{'Idempotency-Key':idempotencyKey},body:JSON.stringify({version:ticket.version})}),
  operationStatus: (id:string) => request<RequestState>(`/requests/${encodeURIComponent(id)}`),
  audit: async (id:string) => { const data=await request<{events:AuditEvent[]}>(`/tickets/${encodeURIComponent(id)}/audit?limit=50`); return data.events; },
  dlq: () => request<{messages:Array<{message_id:string;receive_count?:string;operation:Record<string,unknown>}>}>('/admin/dlq'),
};
