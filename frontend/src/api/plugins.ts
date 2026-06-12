import request from './request';

export interface PluginInfo {
  id: number;
  plugin_id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  icon?: string;
  category: string;
  tags: string[];
  permissions: string[];
  is_official: boolean;
  is_featured: boolean;
  download_count: number;
  rating_avg: number;
  rating_count: number;
  installation?: {
    id: number;
    status: string;
    installed_version: string;
    config: Record<string, unknown>;
    installed_at: string;
    has_update: boolean;
  };
}

export interface PluginCategory {
  key: string;
  label: string;
}

export interface SkillInfo {
  id: number;
  skill_key: string;
  name: string;
  description: string;
  source_type: string;
  version: string;
  is_enabled: boolean;
  is_native: boolean;
  permissions: string[];
  parameters: Record<string, unknown>;
  config_schema: Record<string, unknown>;
  icon?: string;
  tags: string[];
  mcp_server_id?: number;
  mcp_tool_name?: string;
  tenant_config?: Record<string, unknown>;
  tenant_enabled?: boolean;
}

export function listPluginCategories(): Promise<PluginCategory[]> {
  return request.get('/plugins/categories') as Promise<PluginCategory[]>;
}

export function listMarketplace(params?: {
  category?: string;
  keyword?: string;
  featured_only?: boolean;
  page?: number;
  page_size?: number;
}): Promise<{ items: PluginInfo[]; total: number; page: number; page_size: number }> {
  return request.get('/plugins/marketplace', { params }) as Promise<{
    items: PluginInfo[];
    total: number;
    page: number;
    page_size: number;
  }>;
}

export function getPluginDetail(pluginId: string): Promise<PluginInfo & { skills: unknown[]; reviews: unknown[] }> {
  return request.get(`/plugins/${pluginId}`) as Promise<
    PluginInfo & { skills: unknown[]; reviews: unknown[] }
  >;
}

export function listInstalledPlugins(): Promise<PluginInfo[]> {
  return request.get('/plugins/installed') as Promise<PluginInfo[]>;
}

export function installPlugin(pluginId: string): Promise<{ installation_id: number; status: string }> {
  return request.post('/plugins/install', { plugin_id: pluginId }) as Promise<{
    installation_id: number;
    status: string;
  }>;
}

export function uninstallPlugin(pluginId: string): Promise<void> {
  return request.post(`/plugins/${pluginId}/uninstall`) as Promise<void>;
}

export function setPluginStatus(pluginId: string, enabled: boolean): Promise<{ status: string }> {
  return request.put(`/plugins/${pluginId}/status`, { enabled }) as Promise<{ status: string }>;
}

export function updatePluginConfig(
  pluginId: string,
  config: Record<string, unknown>,
): Promise<{ config: Record<string, unknown> }> {
  return request.put(`/plugins/${pluginId}/config`, { config }) as Promise<{
    config: Record<string, unknown>;
  }>;
}

export function addPluginReview(
  pluginId: string,
  rating: number,
  comment?: string,
): Promise<{ rating: number; comment?: string }> {
  return request.post(`/plugins/${pluginId}/reviews`, { rating, comment }) as Promise<{
    rating: number;
    comment?: string;
  }>;
}

export function listSkills(enabledOnly = false): Promise<SkillInfo[]> {
  return request.get('/skills', { params: { enabled_only: enabledOnly } }) as Promise<SkillInfo[]>;
}

export function getSkillDetail(skillKey: string): Promise<SkillInfo> {
  return request.get(`/skills/${encodeURIComponent(skillKey)}`) as Promise<SkillInfo>;
}

export function updateSkillConfig(
  skillKey: string,
  config: Record<string, unknown>,
  enabled?: boolean,
): Promise<{ skill_key: string; config: Record<string, unknown>; is_enabled: boolean }> {
  return request.put(`/skills/${encodeURIComponent(skillKey)}/config`, {
    config,
    enabled,
  }) as Promise<{ skill_key: string; config: Record<string, unknown>; is_enabled: boolean }>;
}

export function setSkillStatus(skillKey: string, enabled: boolean): Promise<{ enabled: boolean }> {
  return request.put(`/skills/${encodeURIComponent(skillKey)}/status`, {
    enabled,
  }) as Promise<{ enabled: boolean }>;
}

export function testSkill(
  skillKey: string,
  parameters: Record<string, unknown>,
): Promise<{ success: boolean; result?: unknown; error?: string; duration_ms?: number }> {
  return request.post(`/skills/${encodeURIComponent(skillKey)}/test`, {
    parameters,
  }) as Promise<{ success: boolean; result?: unknown; error?: string; duration_ms?: number }>;
}
