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

export interface AuditLogQuery {
  action?: string;
  resource_type?: string;
  user_id?: number;
  resource_id?: number;
  start_at?: string;
  end_at?: string;
}

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export function getAuditLogs(
  params?: PageParams & AuditLogQuery,
): Promise<PageResult<AuditLogItem>> {
  return request.get('/audit-logs', { params }) as Promise<PageResult<AuditLogItem>>;
}

/** 导出审计日志文件 */
export async function exportAuditLogs(
  format: 'csv' | 'excel',
  params?: AuditLogQuery,
): Promise<void> {
  const token = localStorage.getItem('token');
  const query = new URLSearchParams();
  if (params?.action) query.set('action', params.action);
  if (params?.resource_type) query.set('resource_type', params.resource_type);
  if (params?.user_id != null) query.set('user_id', String(params.user_id));
  if (params?.resource_id != null) query.set('resource_id', String(params.resource_id));
  if (params?.start_at) query.set('start_at', params.start_at);
  if (params?.end_at) query.set('end_at', params.end_at);

  const suffix = query.toString() ? `?${query.toString()}` : '';
  const response = await fetch(`${baseURL}/audit-logs/export/${format}${suffix}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error('导出失败');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = format === 'csv' ? 'audit_logs.csv' : 'audit_logs.xlsx';
  link.click();
  window.URL.revokeObjectURL(url);
}
