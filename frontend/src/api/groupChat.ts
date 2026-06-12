import request from './request';

/** 群聊成员（动态团队） */
export interface GroupChatMember {
  role: string;
  name: string;
  avatar: string;
  color: string;
  status: 'pending' | 'thinking' | 'working' | 'completed' | 'error' | 'revision' | string;
  current_task?: string | null;
  completed_count?: number;
  total_count?: number;
  is_auditor?: boolean;
  review_round?: number | null;
  reject_reason?: string | null;
}

/** 消息附件 */
export interface MessageAttachment {
  type: 'text' | 'code' | 'image' | 'file' | 'table' | 'chart';
  name: string;
  content: unknown;
  language?: string;
}

/** 交付物附件扩展 */
export interface DeliverableAttachment {
  id: string;
  name: string;
  category: 'final' | 'chart' | 'intermediate' | 'reference';
  fileType: 'md' | 'pdf' | 'png' | 'xlsx' | 'txt' | 'code' | 'chart';
  size: number;
  content: string;
  createBy: string;
}

/** 标准化 Agent 消息 */
export interface AgentMessage {
  id: string;
  timestamp: string;
  sender: {
    id: string;
    name: string;
    role: string;
    avatar: string;
  };
  receiver?: string;
  type: string;
  content: string;
  /** 内容类型，向后兼容：缺省视为 markdown */
  contentType?: 'text' | 'markdown' | 'chart' | 'file' | 'image';
  attachments?: MessageAttachment[];
  /** contentType=chart 时的 ECharts 配置 */
  chartConfig?: Record<string, unknown>;
  metadata?: {
    taskId?: string;
    step?: number;
    duration?: number;
    toolCalls?: unknown[];
    thought?: string;
    [key: string]: unknown;
  };
}

/** 进度步骤 */
export interface ProgressStep {
  key: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'skipped' | string;
}

/** 群聊会话 */
export interface GroupChatSession {
  id: number;
  tenant_id: number;
  user_id: number;
  workflow_id?: number | null;
  execution_id?: number | null;
  title: string;
  task_description: string;
  status: string;
  progress: number;
  current_step: number;
  subtasks: Record<string, unknown>[];
  deliverables: Record<string, unknown>[];
  review_result?: Record<string, unknown> | null;
  review_count: number;
  kb_id?: number | null;
  error_message?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
  members: GroupChatMember[];
  progress_steps: ProgressStep[];
  team_config?: TeamConfig | null;
  messages?: GroupChatMessageRecord[];
}

/** 群聊消息记录 */
export interface GroupChatMessageRecord {
  id: number;
  message_id: string;
  sender_role: string;
  message_type: string;
  content: string;
  payload: AgentMessage;
  created_at: string;
}

/** 团队配置 */
export interface TeamConfig {
  team_id: string;
  task_description: string;
  team_size: number;
  members: Record<string, unknown>[];
  workflow: string;
  max_review_rounds: number;
  template_id?: string;
}

/** 创建群聊会话参数 */
export interface CreateGroupChatParams {
  task: string;
  workflow_id?: number;
  kb_id?: number;
  title?: string;
  template_id?: string;
  team_config?: TeamConfig;
  use_classic_five?: boolean;
}

/** WebSocket 消息 */
export interface GroupChatWsMessage {
  type:
    | 'connected'
    | 'group_chat_message'
    | 'member_status'
    | 'session_update'
    | 'team_formation'
    | 'team_adjusted';
  session_id?: number;
  formation_message?: string;
  team_config?: TeamConfig;
  message?: AgentMessage;
  role?: string;
  status?: string;
  members?: GroupChatMember[];
  progress?: number;
  final_answer?: string;
  error?: string;
}

/** 创建群聊会话 */
export function createGroupChatSession(data: CreateGroupChatParams): Promise<GroupChatSession> {
  return request.post('/group-chat/sessions', data);
}

/** 获取群聊会话详情 */
export function getGroupChatSession(
  sessionId: number,
  includeMessages = true,
): Promise<GroupChatSession> {
  return request.get(`/group-chat/sessions/${sessionId}`, {
    params: { include_messages: includeMessages },
  });
}

/** 获取消息列表 */
export function getGroupChatMessages(sessionId: number): Promise<GroupChatMessageRecord[]> {
  return request.get(`/group-chat/sessions/${sessionId}/messages`);
}

/** 用户发言 */
export function sendGroupChatMessage(
  sessionId: number,
  content: string,
): Promise<GroupChatMessageRecord> {
  return request.post(`/group-chat/sessions/${sessionId}/messages`, { content });
}

/** 取消群聊会话 */
export function cancelGroupChatSession(sessionId: number): Promise<void> {
  return request.post(`/group-chat/sessions/${sessionId}/cancel`) as Promise<void>;
}

/** 人工审核处理 */
export function resolveGroupChatReview(
  sessionId: number,
  action: 'approve' | 'reject',
  comment?: string,
): Promise<GroupChatSession> {
  return request.post(`/group-chat/sessions/${sessionId}/resolve`, {
    action,
    comment,
  }) as Promise<GroupChatSession>;
}

/** 导出群聊会话审计日志 */
export function getGroupChatAuditLogs(
  sessionId: number,
): Promise<{ items: Record<string, unknown>[] }> {
  return request.get(`/group-chat/sessions/${sessionId}/audit-logs`) as Promise<{
    items: Record<string, unknown>[];
  }>;
}

/** 构建群聊 WebSocket URL */
export function buildGroupChatWsUrl(sessionId: number): string {
  const token = localStorage.getItem('token') || '';
  const base = import.meta.env.VITE_WS_BASE_URL || '';
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = base || `${wsProtocol}//${window.location.host}`;
  return `${host}/api/v1/group-chat/ws/${sessionId}?token=${encodeURIComponent(token)}`;
}

/** 角色气泡颜色 */
export const ROLE_BUBBLE_COLORS: Record<string, string> = {
  project_manager: '#1677FF',
  researcher: '#00B42A',
  engineer: '#722ED1',
  analyst: '#FF7D00',
  auditor: '#F53F3F',
  user: '#86909C',
  system: '#C9CDD4',
};
