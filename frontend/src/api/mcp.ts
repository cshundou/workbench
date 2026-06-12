import request from './request';

export interface McpServerInfo {
  id: number;
  name: string;
  transport: string;
  endpoint: string;
  is_builtin: boolean;
  is_active: boolean;
}

export function listMcpServers(): Promise<McpServerInfo[]> {
  return request.get('/mcp/servers') as Promise<McpServerInfo[]>;
}

export function createMcpServer(data: {
  name: string;
  transport: string;
  endpoint: string;
  config?: Record<string, unknown>;
}): Promise<{ id: number; name: string }> {
  return request.post('/mcp/servers', data) as Promise<{ id: number; name: string }>;
}

export function testMcpServer(id: number): Promise<{ success: boolean; error?: string }> {
  return request.post(`/mcp/servers/${id}/test`) as Promise<{ success: boolean; error?: string }>;
}

export function syncMcpTools(id: number): Promise<{ synced_count: number }> {
  return request.post(`/mcp/servers/${id}/sync`) as Promise<{ synced_count: number }>;
}

export function enableBuiltinMcp(): Promise<{ created_count: number }> {
  return request.post('/mcp/builtin/enable') as Promise<{ created_count: number }>;
}
