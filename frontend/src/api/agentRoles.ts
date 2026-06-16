import request from './request';
import type { GroupChatMember } from './groupChat';

/** 专业角色 */
export interface ProfessionalRole {
  id: number;
  tenant_id?: number | null;
  role_id: string;
  name: string;
  avatar: string;
  category: string;
  system_prompt: string;
  tools: string[];
  responsibility: string;
  color: string;
  is_preset: boolean;
  is_builtin: boolean;
  created_by?: number | null;
  created_at: string;
  updated_at: string;
}

/** 团队成员配置 */
export interface TeamMemberConfig {
  role_id: string;
  name: string;
  avatar: string;
  responsibility?: string;
  tools?: string[];
  subtasks?: string[];
  system_prompt?: string;
  color?: string;
  depends_on?: string[];
  parallel_group?: string;
  execution_mode?: 'llm' | 'task';
  task_tools?: string[];
}

/** 团队配置 */
export interface TeamConfig {
  team_id: string;
  task_description: string;
  team_size: number;
  members: TeamMemberConfig[];
  workflow: string;
  max_review_rounds: number;
  domain?: string;
  complexity?: string;
  template_id?: string | number;
}

/** 团队模板 */
export interface TeamTemplateItem {
  id: string | number;
  name: string;
  description?: string;
  scenario?: string;
  team_size?: number;
  is_official?: boolean;
  team_config?: TeamConfig;
}

/** 获取专业角色列表 */
export function listProfessionalRoles(category?: string): Promise<ProfessionalRole[]> {
  return request.get('/professional-roles', { params: { category } });
}

/** 创建自定义角色 */
export function createProfessionalRole(data: {
  role_id: string;
  name: string;
  avatar?: string;
  category?: string;
  system_prompt: string;
  tools?: string[];
  responsibility: string;
  color?: string;
}): Promise<ProfessionalRole> {
  return request.post('/professional-roles', data);
}

/** 更新自定义角色 */
export function updateProfessionalRole(
  id: number,
  data: Partial<{
    name: string;
    avatar: string;
    system_prompt: string;
    tools: string[];
    responsibility: string;
    color: string;
  }>,
): Promise<ProfessionalRole> {
  return request.put(`/professional-roles/${id}`, data);
}

/** 删除自定义角色 */
export function deleteProfessionalRole(id: number): Promise<void> {
  return request.delete(`/professional-roles/${id}`) as Promise<void>;
}

/** 智能组建团队 */
export function buildTeam(data: {
  task: string;
  template_id?: string | number;
  team_config?: TeamConfig;
}): Promise<TeamConfig> {
  return request.post('/team/build', data);
}

/** 预览组队（不创建会话） */
export function previewTeamBuild(data: {
  task: string;
  template_id?: string;
}): Promise<TeamConfig> {
  return request.post('/group-chat/team/preview', data);
}

/** 获取团队模板 */
export function listTeamTemplates(scenario?: string): Promise<{
  official: TeamTemplateItem[];
  custom: TeamTemplateItem[];
}> {
  return request.get('/team/templates', { params: { scenario } });
}

/** 保存团队模板 */
export function saveTeamTemplate(data: {
  name: string;
  description?: string;
  scenario?: string;
  team_config: TeamConfig;
  is_public?: boolean;
}): Promise<TeamTemplateItem> {
  return request.post('/team/templates', data);
}

/** 删除团队模板 */
export function deleteTeamTemplate(id: number): Promise<void> {
  return request.delete(`/team/templates/${id}`) as Promise<void>;
}

/** 调整执行中团队 */
export function adjustTeam(
  sessionId: number,
  members: TeamMemberConfig[],
): Promise<{ members: GroupChatMember[]; team_config: TeamConfig }> {
  return request.post(`/group-chat/sessions/${sessionId}/adjust-team`, { members });
}
