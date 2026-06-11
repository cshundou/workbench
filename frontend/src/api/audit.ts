import request from './request';
import type { PageParams, PageResult } from '@/types/api';

export interface AuditLogItem {
  id: number;
  tenant_id: number;
  user_id?: number | null;
  action: string;
  resource_type?: string | null;
  resource_id?: number | null;
  detail?: Record<string, unknown> | null;
  ip_address?: string | null;
  created_at?: string;
}

export function getAuditLogs(
  params?: PageParams & { action?: string; resource_type?: string },
): Promise<PageResult<AuditLogItem>> {
  return request.get('/audit-logs', { params }) as Promise<PageResult<AuditLogItem>>;
}
