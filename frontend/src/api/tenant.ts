import request from './request';
import type { PageParams, PageResult } from '@/types/api';

export interface TenantInfo {
  id: number;
  name: string;
  domain: string;
  status: number;
  created_at?: string;
  updated_at?: string;
}

export interface CreateTenantParams {
  name: string;
  domain: string;
  status?: number;
}

export interface UpdateTenantParams {
  name?: string;
  domain?: string;
  status?: number;
}

export function getTenants(params?: PageParams): Promise<PageResult<TenantInfo>> {
  return request.get('/tenants', { params }) as Promise<PageResult<TenantInfo>>;
}

export function createTenant(data: CreateTenantParams): Promise<TenantInfo> {
  return request.post('/tenants', data) as Promise<TenantInfo>;
}

export function updateTenant(id: number, data: UpdateTenantParams): Promise<TenantInfo> {
  return request.put(`/tenants/${id}`, data) as Promise<TenantInfo>;
}

export function deleteTenant(id: number): Promise<void> {
  return request.delete(`/tenants/${id}`) as Promise<void>;
}
