export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'DELETED';
export interface Ticket { ticket_id: string; title: string; description: string; priority: Priority; status: TicketStatus; created_by: string; created_at: string; updated_at: string; version: number }
export interface TicketPage { tickets: Ticket[]; next_token?: string }
export interface RequestState { operation_id: string; ticket_id: string; status: string; created_at?: string; completed_at?: string; last_error?: string; ambiguous_at?: string }
export interface AuditEvent { action: string; performed_by: string; performed_at: string; changes?: string | Record<string, unknown>; event_sort: string }
