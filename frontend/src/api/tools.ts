import request from './request';

export interface CustomToolInfo {
  id: number;
  tenant_id: number;
  owner_id: number;
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
  invoke_url: string;
  auth_type: 'none' | 'bearer' | 'api_key';
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface RegisterToolParams {
  name: string;
  description: string;
  parameters_schema?: Record<string, unknown>;
  invoke_url: string;
  auth_type?: 'none' | 'bearer' | 'api_key';
  auth_token?: string;
}

export function listCustomTools(): Promise<CustomToolInfo[]> {
  return request.get('/tools') as Promise<CustomToolInfo[]>;
}

export function registerCustomTool(data: RegisterToolParams): Promise<CustomToolInfo> {
  return request.post('/tools/register', data) as Promise<CustomToolInfo>;
}

export function updateCustomTool(
  id: number,
  data: Partial<RegisterToolParams> & { is_active?: boolean },
): Promise<CustomToolInfo> {
  return request.put(`/tools/${id}`, data) as Promise<CustomToolInfo>;
}

export function deleteCustomTool(id: number): Promise<void> {
  return request.delete(`/tools/${id}`) as Promise<void>;
}

export function testCustomTool(
  id: number,
  parameters: Record<string, unknown>,
): Promise<{ success: boolean; content?: unknown; error?: string }> {
  return request.post(`/tools/${id}/test`, { parameters }) as Promise<{
    success: boolean;
    content?: unknown;
    error?: string;
  }>;
}
